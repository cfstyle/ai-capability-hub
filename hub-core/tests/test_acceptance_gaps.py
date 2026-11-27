"""验收缺口 1~4 全链路真实 HTTP 边界端到端测试

覆盖：
1. 凭据接收方默认不受信任；manifest 只能声明需要凭据；管理员独立确认绑定版本与目标地址；变更后失效重确认；
   生产环境强制 HTTPS；日志不含 session 标识；
2. 工具级凭据要求：同一 TICM 服务下 trading_calendar 免凭据匿名执行（下游不含个人凭据），portfolio_summary 需个人绑定；
3. 模拟 TICM 业务系统与 MCP 服务边界分离：MCP 实际 POST 登录取 Cookie，再携 Cookie 请求持仓；
   两个外部 MCP 客户端并发访问运行中 Hub /mcp（不直接调用中间件/聚合器），A/B 各自隔离，A 改密重登，A 解绑停止持仓请求且 B 不受影响；
4. 门户分别展示已保存（saved）、已验证（verified）、登录失效（invalid）和下游不可用（unavailable）。
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import logging
import socket
import sys
import threading
import time
import zipfile
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from src.main import build_app
from src.registry.models import (
    CredentialFieldSchema,
    CredentialFieldType,
    RegisteredTool,
    ServiceCredentialSchema,
    ServiceRegistration,
    ToolRiskLevel,
)


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_uvicorn_thread(app, host: str = "127.0.0.1") -> tuple[uvicorn.Server, threading.Thread, int]:
    port = _get_free_port()
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 10.0
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://{host}:{port}/healthz", timeout=0.5, trust_env=False)
            if r.status_code == 200:
                return server, thread, port
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"Server on port {port} failed to start")


def _load_module(name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.anyio
async def test_trust_binding_version_endpoint_and_production_transport(tmp_path, monkeypatch):
    """验收缺口 1：默认不受信任、忽略 manifest 自声明、版本/地址变更失效、生产环境强制 HTTPS"""
    admin_key = "test-admin-trust"
    monkeypatch.setenv("HUB_ADMIN_API_KEY", admin_key)
    monkeypatch.setenv("HUB_ENV", "development")
    monkeypatch.setenv("HUB_CREDENTIAL_ENCRYPTION_KEY", "u1_2bHk8Sj2O8B9p-w4Z3o7I_f5V1m8N6Y0x4R2T5Qc=")
    monkeypatch.setenv("HUB_DATABASE_URL", f"sqlite:///{tmp_path / 'trust.db'}")
    monkeypatch.setenv("HUB_UPSTREAM_SERVICES", "[]")

    from src.config import settings, load_config
    load_config.cache_clear()
    settings.admin_api_key = admin_key
    settings.upstream_services = []

    app = build_app()
    hub_srv, hub_th, hub_port = _start_uvicorn_thread(app)
    hub_url = f"http://127.0.0.1:{hub_port}"

    try:
        async with httpx.AsyncClient(base_url=hub_url, trust_env=False, timeout=25.0) as hc:
            # 1. 即使注册/发布载荷尝试自声明 trusted_credential_recipient=True，也必须默认不受信任
            reg_payload = {
                "service_id": "ticm_trust_test",
                "name": "TICM 信任测试",
                "endpoint_url": "http://127.0.0.1:19999/mcp",
                "version": "1.0.0",
                "trusted_credential_recipient": True,
                "credential_schema": {
                    "enabled": True,
                    "auth_type": "username_password",
                    "fields": [
                        {"field_name": "username", "label": "账号", "field_type": "text", "required": True},
                        {"field_name": "password", "label": "密码", "field_type": "password", "required": True},
                    ],
                },
            }
            resp = await hc.post("/api/v1/services/register", json=reg_payload, headers={"X-Admin-Key": admin_key})
            assert resp.status_code == 200
            svc = resp.json()
            assert svc["trusted_credential_recipient"] is False
            assert svc["trusted_credential_version"] is None
            assert svc["trusted_credential_endpoint_url"] is None

            # 检查插件发布 ZIP 同样忽略 manifest 中的 trusted_credential_recipient: true
            from src.gateway.plugin_manager import plugin_manager
            isolated_services = tmp_path / "services"
            isolated_services.mkdir(parents=True, exist_ok=True)
            monkeypatch.setattr(plugin_manager, "services_dir", isolated_services)
            manifest_bytes = json.dumps({
                "service_id": "ticm_zip_trust",
                "name": "ZIP 信任测试",
                "version": "1.0.0",
                "trusted_credential_recipient": True,
                "credential_schema": {"enabled": True, "fields": []},
                "tools": [{"name": "ping", "description": "ping", "risk_level": "L0", "requires_credentials": False}],
            }).encode("utf-8")
            server_bytes = (
                "import os\nfrom fastmcp import FastMCP\nfrom starlette.responses import JSONResponse\n"
                "mcp = FastMCP('zip-trust')\n"
                "@mcp.tool()\nasync def ping() -> dict:\n    return {'ok': True}\n"
                "@mcp.custom_route('/healthz', methods=['GET'])\nasync def hz(req):\n    return JSONResponse({'status': 'ok'})\n"
                "if __name__ == '__main__':\n"
                "    mcp.run(transport='streamable-http', host=os.getenv('MCP_HOST', '127.0.0.1'), port=int(os.getenv('MCP_PORT', '8000')))\n"
            ).encode("utf-8")
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w") as zf:
                zf.writestr("manifest.json", manifest_bytes)
                zf.writestr("server.py", server_bytes)
            try:
                pub = await hc.post(
                    "/api/v1/plugins/publish",
                    files={"file": ("ticm_zip_trust.zip", zbuf.getvalue(), "application/zip")},
                    headers={"X-Admin-Key": admin_key},
                )
                assert pub.status_code == 200, pub.text
                assert pub.json()["trusted_credential_recipient"] is False
            finally:
                plugin_manager.stop_service("ticm_zip_trust")

            # 保存一个需要凭据的工具并授权用户调用
            store = app.state.store
            await store.save_tools(
                "ticm_trust_test",
                [
                    RegisteredTool(
                        id="ticm_trust_test__secret_op",
                        service_id="ticm_trust_test",
                        name="secret_op",
                        description="需凭据操作",
                        risk_level=ToolRiskLevel.L1,
                        requires_credentials=True,
                    )
                ],
            )
            await store.grant_tools("user-a", ["ticm_trust_test__secret_op"])
            await store.save_user_binding("user-a", "ticm_trust_test", {"username": "u", "password": "p"})

            login_a = await hc.post("/api/v1/portal/auth/login", json={"user_id": "user-a", "user_name": "A"})
            token_a = login_a.json()["token"]

            # 未经管理员确认可信前，调用必须被拒绝（不会向外转发凭据）
            app.state.aggregator.mount_service("ticm_trust_test", "http://127.0.0.1:19999/mcp")
            client_a = Client(StreamableHttpTransport(f"{hub_url}/mcp", headers={"Authorization": f"Bearer {token_a}"}))
            async with client_a:
                with pytest.raises(Exception) as exc_untrusted:
                    await client_a.call_tool("ticm_trust_test_secret_op", {})
                assert "trusted credential recipient" in str(exc_untrusted.value)

            # 2. 管理员独立确认可信，绑定 version=1.0.0 与 endpoint_url
            trust_resp = await hc.put(
                "/api/v1/services/ticm_trust_test/credential-trust",
                json={"trusted": True},
                headers={"X-Admin-Key": admin_key},
            )
            assert trust_resp.status_code == 200
            trusted_svc = trust_resp.json()
            assert trusted_svc["trusted_credential_recipient"] is True
            assert trusted_svc["trusted_credential_version"] == "1.0.0"
            assert trusted_svc["trusted_credential_endpoint_url"] == "http://127.0.0.1:19999/mcp"

            # 3. 插件版本变更 -> 可信状态自动失效，须重新确认
            reg_v2 = {**reg_payload, "version": "1.0.1"}
            resp_v2 = await hc.post("/api/v1/services/register", json=reg_v2, headers={"X-Admin-Key": admin_key})
            assert resp_v2.status_code == 200
            assert resp_v2.json()["trusted_credential_recipient"] is False
            assert resp_v2.json()["trusted_credential_version"] is None

            # 4. 重新确认 1.0.1 后变更目标地址 -> 可信状态再次失效
            await hc.put(
                "/api/v1/services/ticm_trust_test/credential-trust",
                json={"trusted": True},
                headers={"X-Admin-Key": admin_key},
            )
            reg_url2 = {**reg_v2, "endpoint_url": "http://127.0.0.1:19998/mcp"}
            resp_url2 = await hc.post("/api/v1/services/register", json=reg_url2, headers={"X-Admin-Key": admin_key})
            assert resp_url2.status_code == 200
            assert resp_url2.json()["trusted_credential_recipient"] is False

            # 5. 生产环境强制 HTTPS 受保护传输
            monkeypatch.setenv("HUB_ENV", "production")
            prod_trust_resp = await hc.put(
                "/api/v1/services/ticm_trust_test/credential-trust",
                json={"trusted": True},
                headers={"X-Admin-Key": admin_key},
            )
            assert prod_trust_resp.status_code == 400
            assert "https://" in prod_trust_resp.json()["detail"]

            # 即使手工置入信任状态，生产环境运行时网关中间件仍阻止通过 http:// 发送个人凭据
            await store.confirm_credential_trust("ticm_trust_test", True, confirmed_by="admin")
            async with Client(StreamableHttpTransport(f"{hub_url}/mcp", headers={"Authorization": f"Bearer {token_a}"})) as c_prod:
                with pytest.raises(Exception) as exc_prod:
                    await c_prod.call_tool("ticm_trust_test_secret_op", {})
                assert "HTTPS" in str(exc_prod.value) or "unprotected transport" in str(exc_prod.value)
    finally:
        hub_srv.should_exit = True
        hub_th.join(timeout=5)


@pytest.mark.anyio
async def test_ticm_real_http_boundaries_and_portal_four_states(tmp_path, monkeypatch, caplog):
    """验收缺口 1(日志无session) + 2(工具级免凭据日历) + 3(分离TICM业务接口+并发双客户端+改密重登+解绑隔离) + 4(门户四状态)"""
    root = Path(__file__).resolve().parents[2]
    backend_mod = _load_module("mock_ticm_backend_e2e", root / "services" / "ticm-mcp" / "mock_ticm_backend.py")
    ticm_mod = _load_module("ticm_mcp_e2e", root / "services" / "ticm-mcp" / "server.py")

    # 1. 启动独立的模拟 TICM 业务后端 HTTP 服务
    backend_app = backend_mod.build_backend_app()
    backend_srv, backend_th, backend_port = _start_uvicorn_thread(backend_app)
    backend_url = f"http://127.0.0.1:{backend_port}"

    # 2. 启动独立的 TICM MCP HTTP 服务，通过 TICM_BACKEND_URL 跨 HTTP 边界调用业务后端
    monkeypatch.setenv("TICM_BACKEND_URL", backend_url)
    ticm_mod.MCP_USER_SESSION_CACHE.clear()
    ticm_asgi = ticm_mod.mcp.http_app(path="/mcp")
    ticm_srv, ticm_th, ticm_port = _start_uvicorn_thread(ticm_asgi)
    ticm_mcp_url = f"http://127.0.0.1:{ticm_port}/mcp"

    # 3. 启动独立运行的 Hub Core HTTP 服务
    admin_key = "test-admin-e2e"
    monkeypatch.setenv("HUB_ADMIN_API_KEY", admin_key)
    monkeypatch.setenv("HUB_ENV", "development")
    monkeypatch.setenv("HUB_CREDENTIAL_ENCRYPTION_KEY", "u1_2bHk8Sj2O8B9p-w4Z3o7I_f5V1m8N6Y0x4R2T5Qc=")
    monkeypatch.setenv("HUB_DATABASE_URL", f"sqlite:///{tmp_path / 'e2e_ticm.db'}")
    monkeypatch.setenv("HUB_UPSTREAM_SERVICES", json.dumps([{"service_id": "ticm", "endpoint_url": ticm_mcp_url, "enabled": True}]))

    from src.config import settings, load_config, UpstreamService
    load_config.cache_clear()
    settings.admin_api_key = admin_key
    settings.upstream_services = [UpstreamService(service_id="ticm", endpoint_url=ticm_mcp_url, enabled=True)]

    hub_app = build_app()
    hub_srv, hub_th, hub_port = _start_uvicorn_thread(hub_app)
    hub_url = f"http://127.0.0.1:{hub_port}"

    try:
        with caplog.at_level(logging.INFO):
            async with httpx.AsyncClient(base_url=hub_url, trust_env=False, timeout=15.0) as hc:
                # 注册带 credential_schema 的 ticm，并由管理员独立确认可信
                reg_resp = await hc.post(
                    "/api/v1/services/register",
                    json={
                        "service_id": "ticm",
                        "name": "TICM 债券资管系统",
                        "endpoint_url": ticm_mcp_url,
                        "version": "1.0.0",
                        "description": "交易日历免凭据，持仓查询需个人绑定",
                        "credential_schema": {
                            "enabled": True,
                            "auth_type": "username_password",
                            "fields": [
                                {"field_name": "username", "label": "用户名", "field_type": "text", "required": True, "secret": False},
                                {"field_name": "password", "label": "密码", "field_type": "password", "required": True, "secret": True},
                            ],
                        },
                    },
                    headers={"X-Admin-Key": admin_key},
                )
                assert reg_resp.status_code == 200
                assert reg_resp.json()["trusted_credential_recipient"] is False

                # 管理员独立确认信任
                trust_resp = await hc.put(
                    "/api/v1/services/ticm/credential-trust",
                    json={"trusted": True},
                    headers={"X-Admin-Key": admin_key},
                )
                assert trust_resp.status_code == 200
                assert trust_resp.json()["trusted_credential_recipient"] is True

                # 刷新工具发现（从运行中的 ticm-mcp /mcp 读取 meta 中的 requires_credentials 与 risk_level）
                ref_resp = await hc.post("/api/v1/services/ticm/refresh", headers={"X-Admin-Key": admin_key})
                assert ref_resp.status_code == 200
                tools_resp = await hc.get("/api/v1/tools?service_id=ticm", headers={"X-Admin-Key": admin_key})
                tool_map = {t["name"]: t for t in tools_resp.json()}
                assert tool_map["ticm__trading_calendar"]["risk_level"] == "L0"
                assert tool_map["ticm__trading_calendar"]["requires_credentials"] is False
                assert tool_map["ticm__portfolio_summary"]["risk_level"] == "L1"
                assert tool_map["ticm__portfolio_summary"]["requires_credentials"] is True

                # --- 缺口 2：匿名外部客户端调用交易日历 ---
                async with Client(StreamableHttpTransport(f"{hub_url}/mcp")) as anon_client:
                    anon_tools = [t.name for t in await anon_client.list_tools()]
                    assert "ticm_ticm__trading_calendar" in anon_tools
                    assert "ticm_ticm__portfolio_summary" not in anon_tools

                    cal_res = await anon_client.call_tool("ticm_ticm__trading_calendar", {"trade_date": "2026-11-25"})
                    cal_json = json.loads(cal_res.content[0].text)
                    assert cal_json["success"] is True
                    assert cal_json["anonymous_execution"] is True
                    assert cal_json["is_trading_day"] is True

                # 断言 TICM 业务后端收到的是匿名日历请求，不含个人凭据与 Cookie
                async with httpx.AsyncClient(base_url=backend_url, trust_env=False) as bc:
                    events = (await bc.get("/ticm/api/test/events")).json()["events"]
                cal_events = [e for e in events if e["endpoint"] == "/ticm/api/calendar"]
                assert len(cal_events) == 1
                assert cal_events[0]["has_personal_credentials"] is False
                assert cal_events[0]["has_session_cookie"] is False

                # --- 缺口 3 & 4：用户 A (dev-user) 与 用户 B (risk-01) 登录、申请、绑定、审批 ---
                tok_a = (await hc.post("/api/v1/portal/auth/login", json={"user_id": "dev-user", "user_name": "张三"})).json()["token"]
                tok_b = (await hc.post("/api/v1/portal/auth/login", json={"user_id": "risk-01", "user_name": "李四"})).json()["token"]

                portfolio_tool_id = tool_map["ticm__portfolio_summary"]["id"]
                req_a = (await hc.post(
                    "/api/v1/portal/permission-requests",
                    json={
                        "service_id": "ticm",
                        "tool_ids": [portfolio_tool_id],
                        "reason": "查询本人组合",
                        "credentials": {"username": "zhangsan", "password": "pwd_zhangsan_123"},
                    },
                    headers={"Authorization": f"Bearer {tok_a}"},
                )).json()
                req_b = (await hc.post(
                    "/api/v1/portal/permission-requests",
                    json={
                        "service_id": "ticm",
                        "tool_ids": [portfolio_tool_id],
                        "reason": "查询本人风控组合",
                        "credentials": {"username": "lisi", "password": "pwd_lisi_456"},
                    },
                    headers={"Authorization": f"Bearer {tok_b}"},
                )).json()

                await hc.post(f"/api/v1/admin/permission-requests/{req_a['id']}/review", json={"status": "approved"}, headers={"X-Admin-Key": admin_key})
                await hc.post(f"/api/v1/admin/permission-requests/{req_b['id']}/review", json={"status": "approved"}, headers={"X-Admin-Key": admin_key})

                # 缺口 4 状态 1：门户展示“已保存”(saved)
                mcps_a_saved = (await hc.get("/api/v1/portal/my-mcps", headers={"Authorization": f"Bearer {tok_a}"})).json()
                assert mcps_a_saved[0]["credential_status"] == "saved"
                assert mcps_a_saved[0]["downstream_status"] == "available"

                # --- 缺口 3：两个外部客户端并发访问运行中的 Hub /mcp ---
                async def call_portfolio(token: str) -> dict:
                    async with Client(StreamableHttpTransport(f"{hub_url}/mcp", headers={"Authorization": f"Bearer {token}"})) as c:
                        res = await c.call_tool("ticm_ticm__portfolio_summary", {"business_date": "2026-11-25"})
                        return json.loads(res.content[0].text)

                res_a, res_b = await asyncio.gather(call_portfolio(tok_a), call_portfolio(tok_b))
                assert res_a["success"] is True
                assert res_a["username"] == "zhangsan"
                assert res_a["portfolio_id"] == "PF_ZHANGSAN_001"
                assert res_a["total_amount"] == 1_428_570_000.0

                assert res_b["success"] is True
                assert res_b["username"] == "lisi"
                assert res_b["portfolio_id"] == "PF_LISI_002"
                assert res_b["total_amount"] == 500_000_000.0

                # 验证 TICM 业务后端确实经历过 POST /ticm/api/login -> GET /ticm/api/positions (携带 Cookie)
                async with httpx.AsyncClient(base_url=backend_url, trust_env=False) as bc:
                    events = (await bc.get("/ticm/api/test/events")).json()["events"]
                login_users = [e["username"] for e in events if e["endpoint"] == "/ticm/api/login" and e["status_code"] == 200]
                pos_events = [e for e in events if e["endpoint"] == "/ticm/api/positions" and e["status_code"] == 200]
                assert "zhangsan" in login_users
                assert "lisi" in login_users
                assert any(e["username"] == "zhangsan" and e["has_session_cookie"] for e in pos_events)
                assert any(e["username"] == "lisi" and e["has_session_cookie"] for e in pos_events)

                # 缺口 4 状态 2：调用成功后门户展示“已验证”(verified)
                mcps_a_verified = (await hc.get("/api/v1/portal/my-mcps", headers={"Authorization": f"Bearer {tok_a}"})).json()
                assert mcps_a_verified[0]["credential_status"] == "verified"

                # --- 缺口 3 & 4 状态 3：A 在 TICM 改密 -> 登录失效 -> 门户展示 invalid -> 更新凭据 -> 重新登录 ---
                async with httpx.AsyncClient(base_url=backend_url, trust_env=False) as bc:
                    chg = await bc.post("/ticm/api/test/change-password", json={"username": "zhangsan", "new_password": "pwd_zhangsan_new"})
                    assert chg.status_code == 200

                stale_res_a = await call_portfolio(tok_a)
                assert stale_res_a["success"] is False
                assert stale_res_a["error_code"] == "INVALID_CREDENTIALS"

                mcps_a_invalid = (await hc.get("/api/v1/portal/my-mcps", headers={"Authorization": f"Bearer {tok_a}"})).json()
                assert mcps_a_invalid[0]["credential_status"] == "invalid"

                # A 在门户更新密码后恢复为 saved，再调用重新 POST 登录成功并恢复为 verified
                upd_resp = await hc.post(
                    "/api/v1/portal/my-mcps/ticm/binding",
                    json={"credentials": {"username": "zhangsan", "password": "pwd_zhangsan_new"}},
                    headers={"Authorization": f"Bearer {tok_a}"},
                )
                assert upd_resp.status_code == 200
                mcps_a_resaved = (await hc.get("/api/v1/portal/my-mcps", headers={"Authorization": f"Bearer {tok_a}"})).json()
                assert mcps_a_resaved[0]["credential_status"] == "saved"

                res_a_relogin = await call_portfolio(tok_a)
                assert res_a_relogin["success"] is True
                assert res_a_relogin["username"] == "zhangsan"

                async with httpx.AsyncClient(base_url=backend_url, trust_env=False) as bc:
                    events_after_relogin = (await bc.get("/ticm/api/test/events")).json()["events"]
                zhangsan_logins = [e for e in events_after_relogin if e["endpoint"] == "/ticm/api/login" and e["username"] == "zhangsan" and e["status_code"] == 200]
                assert len(zhangsan_logins) >= 2

                # --- 缺口 3：A 解绑后不再产生持仓请求，B 不受影响 ---
                del_resp = await hc.delete("/api/v1/portal/my-mcps/ticm/binding", headers={"Authorization": f"Bearer {tok_a}"})
                assert del_resp.status_code == 200

                async with httpx.AsyncClient(base_url=backend_url, trust_env=False) as bc:
                    before_unbind_pos = [
                        e for e in (await bc.get("/ticm/api/test/events")).json()["events"]
                        if e["endpoint"] == "/ticm/api/positions" and e["username"] == "zhangsan"
                    ]

                with pytest.raises(Exception) as exc_unbind:
                    await call_portfolio(tok_a)
                assert "requires personal credentials" in str(exc_unbind.value)

                async with httpx.AsyncClient(base_url=backend_url, trust_env=False) as bc:
                    after_unbind_pos = [
                        e for e in (await bc.get("/ticm/api/test/events")).json()["events"]
                        if e["endpoint"] == "/ticm/api/positions" and e["username"] == "zhangsan"
                    ]
                assert len(after_unbind_pos) == len(before_unbind_pos)

                # B 并发/后续调用完全不受 A 解绑影响
                res_b_after = await call_portfolio(tok_b)
                assert res_b_after["success"] is True
                assert res_b_after["username"] == "lisi"
                assert res_b_after["portfolio_id"] == "PF_LISI_002"

                # --- 缺口 4 状态 4：下游不可用展示 ---
                backend_srv.should_exit = True
                backend_th.join(timeout=5)
                down_res_b = await call_portfolio(tok_b)
                assert down_res_b["success"] is False
                assert down_res_b["error_code"] == "DOWNSTREAM_UNAVAILABLE"

                mcps_b_down = (await hc.get("/api/v1/portal/my-mcps", headers={"Authorization": f"Bearer {tok_b}"})).json()
                assert mcps_b_down[0]["downstream_status"] == "unavailable"

            # --- 缺口 1：确认所有日志中没有任何 session 标识或密码明文 ---
            all_logs = "\n".join(rec.getMessage() for rec in caplog.records)
            assert "sess_" not in all_logs
            assert "ticm_session" not in all_logs
            assert "pwd_zhangsan_123" not in all_logs
            assert "pwd_zhangsan_new" not in all_logs
            assert "pwd_lisi_456" not in all_logs
    finally:
        hub_srv.should_exit = True
        ticm_srv.should_exit = True
        backend_srv.should_exit = True
        hub_th.join(timeout=5)
        ticm_th.join(timeout=5)
        backend_th.join(timeout=5)


@pytest.mark.anyio
async def test_tool_level_apply_summary_and_refresh_preserves_credentials(tmp_path, monkeypatch):
    """补充回归：
    1. 同服务并存“需审批但免个人凭据”与“需个人凭据”工具时，my-mcps 按用户实际申请/授权工具判定是否需要凭据；
    2. 仅在 ZIP manifest.json 声明 requires_credentials=True（server.py 无 meta）时，发布并执行 refresh 刷新后仍保留凭据要求，原用户仍能携带本人账号查询。
    """
    admin_key = "test-admin-refresh-creds"
    monkeypatch.setenv("HUB_ADMIN_API_KEY", admin_key)
    monkeypatch.setenv("HUB_ENV", "development")
    monkeypatch.setenv("HUB_CREDENTIAL_ENCRYPTION_KEY", "u1_2bHk8Sj2O8B9p-w4Z3o7I_f5V1m8N6Y0x4R2T5Qc=")
    monkeypatch.setenv("HUB_DATABASE_URL", f"sqlite:///{tmp_path / 'refresh_creds.db'}")
    monkeypatch.setenv("HUB_UPSTREAM_SERVICES", "[]")

    from src.config import settings, load_config
    from src.gateway.plugin_manager import plugin_manager
    load_config.cache_clear()
    settings.admin_api_key = admin_key
    settings.upstream_services = []

    isolated_services = tmp_path / "services"
    isolated_services.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(plugin_manager, "services_dir", isolated_services)

    app = build_app()
    hub_srv, hub_th, hub_port = _start_uvicorn_thread(app)
    hub_url = f"http://127.0.0.1:{hub_port}"

    svc_id = "mixed_manifest_svc"
    try:
        manifest_bytes = json.dumps({
            "manifest_version": "1.0.0",
            "service_id": svc_id,
            "name": "混合凭据声明插件",
            "version": "1.0.0",
            "credential_schema": {
                "enabled": True,
                "auth_type": "username_password",
                "fields": [
                    {"field_name": "username", "label": "业务账号", "field_type": "text", "required": True, "secret": False},
                    {"field_name": "password", "label": "业务密码", "field_type": "password", "required": True, "secret": True},
                ],
            },
            "tools": [
                {
                    "name": "approval_only_report",
                    "description": "需平台审批但无需个人业务账号的汇总报表",
                    "risk_level": "L1",
                    "requires_credentials": False,
                },
                {
                    "name": "personal_positions",
                    "description": "仅在 manifest 声明 requires_credentials 的个人持仓查询",
                    "risk_level": "L1",
                    "requires_credentials": True,
                },
            ],
        }).encode("utf-8")

        # 注意：故意不在 @mcp.tool() 装饰器中写 meta，仅依靠 manifest.json 声明 requires_credentials
        server_bytes = (
            "import json, os\n"
            "from fastmcp import FastMCP\n"
            "from fastmcp.server.dependencies import get_http_request\n"
            "from starlette.responses import JSONResponse\n"
            "mcp = FastMCP('mixed-manifest')\n"
            "@mcp.tool()\n"
            "async def approval_only_report() -> dict:\n"
            "    req = get_http_request()\n"
            "    return {'success': True, 'has_creds_header': 'x-hub-user-credentials' in {k.lower() for k in req.headers.keys()}}\n"
            "@mcp.tool()\n"
            "async def personal_positions() -> dict:\n"
            "    req = get_http_request()\n"
            "    raw = req.headers.get('x-hub-user-credentials')\n"
            "    if not raw:\n"
            "        return {'success': False, 'error_code': 'UNAUTHORIZED'}\n"
            "    creds = json.loads(raw)\n"
            "    return {'success': True, 'username': creds.get('username')}\n"
            "@mcp.custom_route('/healthz', methods=['GET'])\n"
            "async def hz(req):\n"
            "    return JSONResponse({'status': 'ok'})\n"
            "if __name__ == '__main__':\n"
            "    mcp.run(transport='streamable-http', host=os.getenv('MCP_HOST', '127.0.0.1'), port=int(os.getenv('MCP_PORT', '8000')))\n"
        ).encode("utf-8")

        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w") as zf:
            zf.writestr("manifest.json", manifest_bytes)
            zf.writestr("server.py", server_bytes)

        async with httpx.AsyncClient(base_url=hub_url, trust_env=False, timeout=25.0) as hc:
            pub = await hc.post(
                "/api/v1/plugins/publish",
                files={"file": (f"{svc_id}.zip", zbuf.getvalue(), "application/zip")},
                headers={"X-Admin-Key": admin_key},
            )
            assert pub.status_code == 200, pub.text

            trust = await hc.put(
                f"/api/v1/services/{svc_id}/credential-trust",
                json={"trusted": True},
                headers={"X-Admin-Key": admin_key},
            )
            assert trust.status_code == 200

            # 门户详情应透出工具级 requires_credentials 布尔值
            detail = (await hc.get(f"/api/v1/portal/capabilities/{svc_id}")).json()
            detail_tool_map = {t["name"]: t for t in detail["tools"]}
            assert detail_tool_map["approval_only_report"]["requires_credentials"] is False
            assert detail_tool_map["personal_positions"]["requires_credentials"] is True

            # 用户 U1 只申请“需审批但免凭据”工具，不传 credentials
            tok_u1 = (await hc.post("/api/v1/portal/auth/login", json={"user_id": "u1-nocred", "user_name": "U1"})).json()["token"]
            req_u1 = (await hc.post(
                "/api/v1/portal/permission-requests",
                json={
                    "service_id": svc_id,
                    "tool_ids": [detail_tool_map["approval_only_report"]["id"]],
                    "reason": "只需要免凭据审批报表",
                },
                headers={"Authorization": f"Bearer {tok_u1}"},
            )).json()
            assert req_u1["has_credential_binding"] is False
            await hc.post(f"/api/v1/admin/permission-requests/{req_u1['id']}/review", json={"status": "approved"}, headers={"X-Admin-Key": admin_key})

            # “我的 MCP”摘要应按所申请/获批工具判定，显示不需要个人凭据（not_required），而非 missing
            mcps_u1 = (await hc.get("/api/v1/portal/my-mcps", headers={"Authorization": f"Bearer {tok_u1}"})).json()
            assert len(mcps_u1) == 1
            assert mcps_u1[0]["requires_credentials"] is False
            assert mcps_u1[0]["credential_status"] == "not_required"

            async with Client(StreamableHttpTransport(f"{hub_url}/mcp", headers={"Authorization": f"Bearer {tok_u1}"})) as c_u1:
                r1 = await c_u1.call_tool(f"{svc_id}_approval_only_report", {})
                r1_json = json.loads(r1.content[0].text)
                assert r1_json["success"] is True
                assert r1_json["has_creds_header"] is False

            # 用户 U2 申请需要凭据的 personal_positions 并绑定本人账号
            tok_u2 = (await hc.post("/api/v1/portal/auth/login", json={"user_id": "u2-withcred", "user_name": "U2"})).json()["token"]
            req_u2 = (await hc.post(
                "/api/v1/portal/permission-requests",
                json={
                    "service_id": svc_id,
                    "tool_ids": [detail_tool_map["personal_positions"]["id"]],
                    "reason": "查询个人持仓",
                    "credentials": {"username": "zhangsan", "password": "pwd_zhangsan_123"},
                },
                headers={"Authorization": f"Bearer {tok_u2}"},
            )).json()
            await hc.post(f"/api/v1/admin/permission-requests/{req_u2['id']}/review", json={"status": "approved"}, headers={"X-Admin-Key": admin_key})

            # 执行刷新（模拟管理员在控制台点击刷新工具定义）
            ref = await hc.post(f"/api/v1/services/{svc_id}/refresh", headers={"X-Admin-Key": admin_key})
            assert ref.status_code == 200, ref.text

            # 刷新后 tools/list 元数据仍保留 personal_positions.requires_credentials == True
            tools_after_refresh = {
                t["name"]: t
                for t in (await hc.get(f"/api/v1/tools?service_id={svc_id}", headers={"X-Admin-Key": admin_key})).json()
            }
            assert tools_after_refresh["personal_positions"]["requires_credentials"] is True
            assert tools_after_refresh["approval_only_report"]["requires_credentials"] is False

            # 即使移除本地 manifest.json 后再刷新，数据库 preserve_policies=True 依然保留凭据声明不退化
            (isolated_services / svc_id / "manifest.json").unlink()
            ref2 = await hc.post(f"/api/v1/services/{svc_id}/refresh", headers={"X-Admin-Key": admin_key})
            assert ref2.status_code == 200
            tools_after_refresh2 = {
                t["name"]: t
                for t in (await hc.get(f"/api/v1/tools?service_id={svc_id}", headers={"X-Admin-Key": admin_key})).json()
            }
            assert tools_after_refresh2["personal_positions"]["requires_credentials"] is True

            # 刷新后原用户 U2 仍能携带本人账号正常查询
            async with Client(StreamableHttpTransport(f"{hub_url}/mcp", headers={"Authorization": f"Bearer {tok_u2}"})) as c_u2:
                r2 = await c_u2.call_tool(f"{svc_id}_personal_positions", {})
                r2_json = json.loads(r2.content[0].text)
                assert r2_json["success"] is True
                assert r2_json["username"] == "zhangsan"
    finally:
        plugin_manager.stop_service(svc_id)
        hub_srv.should_exit = True
        hub_th.join(timeout=5)


@pytest.mark.anyio
async def test_production_encryption_key_required_and_persists_across_rebuild(tmp_path, monkeypatch):
    """部署安全回归：
    1. HUB_ENV=production 缺少 HUB_CREDENTIAL_ENCRYPTION_KEY 时拒绝加解密托管凭据；
    2. 配置固定 HUB_CREDENTIAL_ENCRYPTION_KEY 后，模拟保留 SQLite 数据卷重建服务进程，原用户绑定凭据仍可正常解密。
    """
    from src.governance.crypto import encrypt_credentials, decrypt_credentials, reset_fernet_cache
    from src.config import settings, load_config

    db_file = tmp_path / "prod_persist.db"
    prod_key = "u1_2bHk8Sj2O8B9p-w4Z3o7I_f5V1m8N6Y0x4R2T5Qc="

    # 1. 生产模式缺密钥 -> 拒绝托管凭据
    monkeypatch.setenv("HUB_ENV", "production")
    monkeypatch.delenv("HUB_CREDENTIAL_ENCRYPTION_KEY", raising=False)
    reset_fernet_cache()
    with pytest.raises(RuntimeError, match="HUB_CREDENTIAL_ENCRYPTION_KEY"):
        encrypt_credentials({"username": "zhangsan", "password": "pwd_zhangsan_123"})

    # 2. 生产模式配置固定密钥 -> 绑定入库
    monkeypatch.setenv("HUB_CREDENTIAL_ENCRYPTION_KEY", prod_key)
    monkeypatch.setenv("HUB_ADMIN_API_KEY", "prod-admin-key")
    monkeypatch.setenv("HUB_MCP_JWT_SECRET", "prod-mcp-jwt-secret-9f8e7d6c")
    monkeypatch.setenv("HUB_RGONE_JWT_SECRET", "prod-rgone-jwt-secret-1a2b3c4d")
    monkeypatch.setenv("HUB_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("HUB_UPSTREAM_SERVICES", "[]")
    reset_fernet_cache()
    load_config.cache_clear()
    settings.admin_api_key = "prod-admin-key"
    settings.upstream_services = []

    app1 = build_app()
    srv1, th1, _ = _start_uvicorn_thread(app1)
    try:
        await app1.state.store.register_service(
            ServiceRegistration(
                service_id="ticm_prod",
                name="TICM Prod",
                endpoint_url="https://ticm.internal/mcp",
                version="1.0.0",
                credential_schema=ServiceCredentialSchema(enabled=True, fields=[]),
            )
        )
        await app1.state.store.save_user_binding(
            "dev-user",
            "ticm_prod",
            {"username": "zhangsan", "password": "pwd_zhangsan_123"},
        )
    finally:
        srv1.should_exit = True
        th1.join(timeout=5)

    # 3. 模拟保留数据卷重建容器：清空进程内 Fernet 缓存并构建全新 Hub 实例指向同一 db_file 与同密钥
    reset_fernet_cache()
    load_config.cache_clear()
    app2 = build_app()
    srv2, th2, _ = _start_uvicorn_thread(app2)
    try:
        decrypted = await app2.state.store.get_decrypted_credentials("dev-user", "ticm_prod")
        assert decrypted is not None
        creds, ver = decrypted
        assert creds == {"username": "zhangsan", "password": "pwd_zhangsan_123"}
        assert ver == 1
        # 确保直调 decrypt_credentials 也一致
        assert decrypt_credentials(encrypt_credentials(creds)) == creds
    finally:
        srv2.should_exit = True
        th2.join(timeout=5)
        reset_fernet_cache()
