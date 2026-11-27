"""RgOne 与 AI Capability Hub 认证互通、统计对齐及即时吊销集成测试"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.config import HubConfig, load_config
from src.governance.auth import create_access_token
from src.main import build_app
from src.registry.models import RegisteredTool, ServiceRegistration, ToolRiskLevel


def _make_rgone_jwt(
    *,
    secret: str,
    sub: str,
    role: str,
    iss: str = "rgone",
    name: str = "测试员工",
    iat_offset: int = 0,
) -> str:
    now = datetime.now(timezone.utc) + timedelta(seconds=iat_offset)
    payload = {
        "sub": sub,
        "name": name,
        "role": role,
        "iss": iss,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=2)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def integrated_client(tmp_path, monkeypatch):
    rgone_secret = "test-rgone-shared-jwt-secret-9988"
    mcp_secret = "test-hub-mcp-jwt-secret-7766"
    internal_secret = "test-internal-sync-secret-5544"

    monkeypatch.setenv("HUB_ENV", "development")
    monkeypatch.setenv("HUB_DATABASE_URL", f"sqlite:///{tmp_path / 'rgone_hub_test.db'}")
    monkeypatch.setenv("HUB_UPSTREAM_SERVICES", "[]")
    monkeypatch.setenv("HUB_RGONE_JWT_SECRET", rgone_secret)
    monkeypatch.setenv("HUB_MCP_JWT_SECRET", mcp_secret)
    monkeypatch.setenv("HUB_INTERNAL_SERVICE_SECRET", internal_secret)
    monkeypatch.delenv("HUB_ADMIN_API_KEY", raising=False)

    load_config.cache_clear()
    app = build_app()
    with TestClient(app) as client:
        yield client, app.state.store, rgone_secret, mcp_secret, internal_secret


def test_production_jwt_secret_validation(monkeypatch):
    """生产环境强校验：禁止空密钥、默认占位密钥或两个密钥相同"""
    monkeypatch.setenv("HUB_ENV", "production")
    monkeypatch.setenv("HUB_MCP_JWT_SECRET", "prod-mcp-secret-111")
    monkeypatch.setenv("HUB_RGONE_JWT_SECRET", "prod-mcp-secret-111")
    with pytest.raises(ValidationError, match="不可相同"):
        HubConfig()

    monkeypatch.setenv("HUB_RGONE_JWT_SECRET", "")
    with pytest.raises(ValidationError, match="HUB_RGONE_JWT_SECRET"):
        HubConfig()

    monkeypatch.setenv("HUB_MCP_JWT_SECRET", "hub-dev-secret-change-me")
    monkeypatch.setenv("HUB_RGONE_JWT_SECRET", "prod-rgone-secret-222")
    with pytest.raises(ValidationError, match="HUB_MCP_JWT_SECRET"):
        HubConfig()


def test_rgone_jwt_routing_and_admin_access_without_static_key(integrated_client):
    """按 iss 严格路由：员工 JWT 换领 MCP Token 但无法进后台；管理员 JWT 无静态 API Key 也可进后台"""
    client, _store, rgone_secret, _mcp_secret, _internal_secret = integrated_client

    emp_jwt = _make_rgone_jwt(secret=rgone_secret, sub="06700956", role="employee", name="陈飞")
    admin_jwt = _make_rgone_jwt(secret=rgone_secret, sub="admin", role="admin", name="admin")

    # 1. 员工 JWT 访问 /portal/my-config -> 成功识别身份并签发 iss=ai-capability-hub 的 ide-client Token
    cfg_resp = client.get("/api/v1/portal/my-config", headers={"Authorization": f"Bearer {emp_jwt}"})
    assert cfg_resp.status_code == 200
    cfg = cfg_resp.json()
    assert cfg["is_guest"] is False
    assert cfg["user_id"] == "06700956"
    assert cfg["user_name"] == "陈飞"
    assert cfg["token"]

    # 2. 员工 JWT 访问管理端 -> 403 拒绝（绝不因为共享同一密钥而越权）
    emp_admin_resp = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {emp_jwt}"})
    assert emp_admin_resp.status_code == 403

    # 3. 管理员 JWT（即使未配置 HUB_ADMIN_API_KEY）-> 成功访问管理接口
    adm_resp = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {admin_jwt}"})
    assert adm_resp.status_code == 200

    # 4. 缺失或未知 iss 的 Token -> 拒绝（返回 401/403）
    no_iss = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600},
        rgone_secret,
        algorithm="HS256",
    )
    bad_resp = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {no_iss}"})
    assert bad_resp.status_code in (401, 403)


def test_dashboard_summary_matches_invocation_logs(integrated_client):
    """/dashboard/summary 统计与 /portal/overview 对齐，且精确匹配 LOWER(result_status)='success'"""
    client, store, rgone_secret, _mcp_secret, _internal_secret = integrated_client
    admin_jwt = _make_rgone_jwt(secret=rgone_secret, sub="admin", role="admin")

    async def _seed_logs():
        await store.register_service(
            ServiceRegistration(
                service_id="demo_svc",
                name="Demo",
                endpoint_url="http://127.0.0.1:9999/mcp",
            )
        )
        await store.save_tools(
            "demo_svc",
            [RegisteredTool(service_id="demo_svc", name="ping", risk_level=ToolRiskLevel.L0)],
        )
        await store.save_invocation_log({
            "user_id": "06700956",
            "client_id": "ide-client",
            "service_id": "demo_svc",
            "tool_name": "demo_svc__ping",
            "params_summary": {},
            "result_status": "success",
            "duration_ms": 12.0,
        })
        await store.save_invocation_log({
            "user_id": "06700956",
            "client_id": "ide-client",
            "service_id": "demo_svc",
            "tool_name": "demo_svc__ping",
            "params_summary": {},
            "result_status": "SUCCESS",
            "duration_ms": 15.0,
        })
        # 异常文本中包含 success 字样，不应被误判为成功
        await store.save_invocation_log({
            "user_id": "06700956",
            "client_id": "ide-client",
            "service_id": "demo_svc",
            "tool_name": "demo_svc__ping",
            "params_summary": {},
            "result_status": "exception: upstream failed after success check",
            "duration_ms": 30.0,
        })

    asyncio.run(_seed_logs())

    dash = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {admin_jwt}"}).json()
    portal = client.get("/api/v1/portal/overview").json()
    assert dash["calls_total"] == 3
    assert dash["calls_success"] == 2
    assert dash["calls_failed"] == 1
    assert portal["total_calls"] == dash["calls_total"]
    assert sum(d["calls"] for d in portal["daily_trends"]) == 3
    assert sum(d["success_calls"] for d in portal["daily_trends"]) == 2


def test_user_revocation_blocks_web_jwt_and_ide_mcp_token(integrated_client):
    """停用员工后 Web JWT 与 ide-client 长效 Token 均瞬间被拒（不降级为 guest），复职后旧 Token 依然失效"""
    client, _store, rgone_secret, _mcp_secret, internal_secret = integrated_client

    emp_jwt = _make_rgone_jwt(secret=rgone_secret, sub="06701099", role="employee", iat_offset=-10)
    ide_token = client.get(
        "/api/v1/portal/my-config",
        headers={"Authorization": f"Bearer {emp_jwt}"},
    ).json()["token"]
    assert ide_token

    # 1. 调用内部吊销接口停用 06701099
    rev_resp = client.post(
        "/api/v1/internal/users/06701099/revoke",
        json={"reason": "employee_disabled"},
        headers={"X-Internal-Secret": internal_secret},
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["is_active"] is False

    # 2. 原 Web JWT 与 ide-client Token 均被直接 401 拦截（即使访问公开接口或 /mcp）
    r1 = client.get("/api/v1/portal/my-config", headers={"Authorization": f"Bearer {emp_jwt}"})
    assert r1.status_code == 401
    r2 = client.post("/mcp", headers={"Authorization": f"Bearer {ide_token}"})
    assert r2.status_code == 401

    # 3. 管理员复职恢复 06701099
    res_resp = client.post(
        "/api/v1/internal/users/06701099/restore",
        json={"reason": "employee_restored"},
        headers={"X-Internal-Secret": internal_secret},
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["is_active"] is True

    # 4. 停用前签发的旧 ide_token 仍受 revoked_before 水位线拦截（严防复活）
    r_old = client.post("/mcp", headers={"Authorization": f"Bearer {ide_token}"})
    assert r_old.status_code == 401

    # 5. 复职后新签发（iat > revoked_before）的 Token 恢复可用
    new_emp_jwt = _make_rgone_jwt(secret=rgone_secret, sub="06701099", role="employee", iat_offset=5)
    r_new = client.get("/api/v1/portal/my-config", headers={"Authorization": f"Bearer {new_emp_jwt}"})
    assert r_new.status_code == 200
    assert r_new.json()["user_id"] == "06701099"


def test_internal_issue_ide_token_and_revocation_block(integrated_client):
    """内部 /ide-token 接口须经 X-Internal-Secret 鉴权，停用员工返回 403，在职员工由 Hub 独立密钥签发"""
    client, _store, _rgone_secret, mcp_secret, internal_secret = integrated_client

    r_bad = client.post(
        "/api/v1/internal/users/06700956/ide-token",
        headers={"X-Internal-Secret": "wrong-secret"},
    )
    assert r_bad.status_code == 403

    r_ok = client.post(
        "/api/v1/internal/users/06700956/ide-token",
        headers={"X-Internal-Secret": internal_secret},
    )
    assert r_ok.status_code == 200
    data = r_ok.json()
    assert data["user_id"] == "06700956"
    claims = jwt.decode(data["token"], mcp_secret, algorithms=["HS256"])
    assert claims["iss"] == "ai-capability-hub"
    assert claims["client_id"] == "ide-client"
    assert claims["sub"] == "06700956"

    # 停用员工后禁止签发 ide-token
    client.post(
        "/api/v1/internal/users/06700956/revoke",
        json={"reason": "disabled"},
        headers={"X-Internal-Secret": internal_secret},
    )
    r_disabled = client.post(
        "/api/v1/internal/users/06700956/ide-token",
        headers={"X-Internal-Secret": internal_secret},
    )
    assert r_disabled.status_code == 403


def test_user_service_toggle_filters_list_tools_and_blocks_call_tool(integrated_client):
    """个人装配开关关闭后，仅隐藏/拦截当前用户的工具（含 L0），不影响其他员工"""
    from types import SimpleNamespace
    from src.governance.auth import TokenPayload, current_user_cv
    from src.governance.middleware import GovernanceMiddleware
    from src.registry.models import ServiceStatus

    client, store, rgone_secret, _mcp_secret, _internal_secret = integrated_client
    emp1_jwt = _make_rgone_jwt(secret=rgone_secret, sub="06700956", role="employee")
    emp2_jwt = _make_rgone_jwt(secret=rgone_secret, sub="06701099", role="employee")

    async def _seed():
        await store.register_service(
            ServiceRegistration(
                service_id="alpha_svc",
                name="Alpha Service",
                endpoint_url="http://127.0.0.1:9999/mcp",
            )
        )
        await store.update_service_status("alpha_svc", ServiceStatus.ACTIVE)
        await store.save_tools(
            "alpha_svc",
            [RegisteredTool(service_id="alpha_svc", name="hello", risk_level=ToolRiskLevel.L0)],
        )

    asyncio.run(_seed())

    # 默认开启语义
    caps_before = client.get(
        "/api/v1/portal/capabilities",
        headers={"Authorization": f"Bearer {emp1_jwt}"},
    ).json()
    assert any(c["id"] == "alpha_svc" and c["user_enabled"] is True for c in caps_before)

    # emp1 关闭 alpha_svc 个人装配开关
    r_off = client.put(
        "/api/v1/portal/my-mcps/alpha_svc/toggle",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {emp1_jwt}"},
    )
    assert r_off.status_code == 200
    assert r_off.json()["user_enabled"] is False

    caps_emp1 = client.get(
        "/api/v1/portal/capabilities",
        headers={"Authorization": f"Bearer {emp1_jwt}"},
    ).json()
    caps_emp2 = client.get(
        "/api/v1/portal/capabilities",
        headers={"Authorization": f"Bearer {emp2_jwt}"},
    ).json()
    assert any(c["id"] == "alpha_svc" and c["user_enabled"] is False for c in caps_emp1)
    assert any(c["id"] == "alpha_svc" and c["user_enabled"] is True for c in caps_emp2)

    mw = GovernanceMiddleware(store=store)

    async def _verify_middleware():
        fake_tool = SimpleNamespace(name="alpha_svc__hello")
        ctx_list = SimpleNamespace(message=SimpleNamespace())

        async def _call_next_list(_ctx):
            return [fake_tool]

        # emp1 被过滤
        tok1 = current_user_cv.set(
            TokenPayload(sub="06700956", client_id="ide-client", scopes=["hub:user"])
        )
        try:
            emp1_tools = await mw.on_list_tools(ctx_list, _call_next_list)
            assert len(emp1_tools) == 0

            ctx_call = SimpleNamespace(message=SimpleNamespace(name="alpha_svc__hello", arguments={}))
            async def _call_next_exec(_ctx):
                return {"ok": True}

            with pytest.raises(PermissionError, match="disabled in your personal settings"):
                await mw.on_call_tool(ctx_call, _call_next_exec)
        finally:
            current_user_cv.reset(tok1)

        # emp2 仍可见 L0 工具
        tok2 = current_user_cv.set(
            TokenPayload(sub="06701099", client_id="ide-client", scopes=["hub:user"])
        )
        try:
            emp2_tools = await mw.on_list_tools(ctx_list, _call_next_list)
            assert len(emp2_tools) == 1
        finally:
            current_user_cv.reset(tok2)

    asyncio.run(_verify_middleware())

    # 重新开启开关后恢复可见
    r_on = client.put(
        "/api/v1/portal/my-mcps/alpha_svc/toggle",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {emp1_jwt}"},
    )
    assert r_on.status_code == 200 and r_on.json()["user_enabled"] is True


def test_stateless_http_mcp_without_session_id(integrated_client):
    """确认开启 stateless_http=True 后，无需携带 Mcp-Session-Id 也可连续无状态调用 /mcp"""
    client, _store, rgone_secret, _mcp_secret, _internal_secret = integrated_client
    emp_jwt = _make_rgone_jwt(secret=rgone_secret, sub="06700956", role="employee")
    headers = {
        "Authorization": f"Bearer {emp_jwt}",
        "Accept": "application/json, text/event-stream",
    }

    init_resp = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        },
    )
    assert init_resp.status_code == 200

    # 不带 Mcp-Session-Id 直接发 tools/list 依然成功（无状态模式）
    list_resp = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert list_resp.status_code == 200
    assert "tools" in list_resp.text


def test_startup_ticm_manifest_sync_and_backfill_preserves_trust(tmp_path, monkeypatch):
    """启动时自动同步 services/ticm-mcp/manifest.json 的凭据字段与工具策略，并在旧库平滑补全时不覆盖信任状态"""
    import json

    db_file = tmp_path / "ticm_manifest_sync.db"
    rgone_secret = "test-rgone-shared-jwt-secret-9988"
    monkeypatch.setenv("HUB_ENV", "development")
    monkeypatch.setenv("HUB_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("HUB_UPSTREAM_SERVICES", json.dumps([
        {"service_id": "ticm", "endpoint_url": "http://127.0.0.1:18081/mcp", "enabled": True}
    ]))
    monkeypatch.setenv("HUB_RGONE_JWT_SECRET", rgone_secret)
    monkeypatch.setenv("HUB_MCP_JWT_SECRET", "test-hub-mcp-jwt-secret-7766")
    monkeypatch.setenv("HUB_INTERNAL_SERVICE_SECRET", "test-internal-sync-secret-5544")
    monkeypatch.delenv("HUB_ADMIN_API_KEY", raising=False)

    # 1. 全新数据库启动：应自动写入 manifest.json 中的 credential_schema 与 ticm__portfolio_summary (L1, requires_credentials=True)
    load_config.cache_clear()
    app1 = build_app()
    with TestClient(app1):
        svc = asyncio.run(app1.state.store.get_service("ticm"))
        assert svc is not None
        assert svc.credential_schema is not None
        assert svc.credential_schema.enabled is True
        labels = [f.label for f in svc.credential_schema.fields]
        assert "TICM 用户名" in labels
        assert "TICM 登录密码" in labels

        tools = asyncio.run(app1.state.store.list_tools("ticm"))
        portfolio_tool = next((t for t in tools if "portfolio_summary" in t.name), None)
        assert portfolio_tool is not None
        assert portfolio_tool.risk_level == ToolRiskLevel.L1
        assert portfolio_tool.requires_credentials is True

    # 2. 旧数据库已存在 ticm 但 credential_schema 为空、工具仍为默认 L0/False，且管理员已开启 trusted_credential_recipient=True
    db_backfill = tmp_path / "ticm_backfill.db"
    monkeypatch.setenv("HUB_DATABASE_URL", f"sqlite:///{db_backfill}")
    monkeypatch.setenv("HUB_UPSTREAM_SERVICES", "[]")
    load_config.cache_clear()
    seed_app = build_app()
    with TestClient(seed_app):
        async def _seed_old_db():
            await seed_app.state.store.register_service(
                ServiceRegistration(
                    service_id="ticm",
                    name="TICM MCP Server",
                    endpoint_url="http://127.0.0.1:18081/mcp",
                    description="Auto-configured upstream service ticm",
                    credential_schema=None,
                )
            )
            await seed_app.state.store.confirm_credential_trust("ticm", True, confirmed_by="admin")
            await seed_app.state.store.save_tools(
                "ticm",
                [
                    RegisteredTool(
                        service_id="ticm",
                        name="ticm__portfolio_summary",
                        risk_level=ToolRiskLevel.L0,
                        requires_credentials=False,
                    )
                ],
                preserve_policies=False,
            )

        asyncio.run(_seed_old_db())

    # 携带 upstream ticm 重新启动，验证平滑补全且保留 trusted_credential_recipient=True
    monkeypatch.setenv("HUB_UPSTREAM_SERVICES", json.dumps([
        {"service_id": "ticm", "endpoint_url": "http://127.0.0.1:18081/mcp", "enabled": True}
    ]))
    load_config.cache_clear()
    app2 = build_app()
    with TestClient(app2):
        svc2 = asyncio.run(app2.state.store.get_service("ticm"))
        assert svc2 is not None
        assert svc2.credential_schema is not None
        assert svc2.credential_schema.enabled is True
        assert [f.field_name for f in svc2.credential_schema.fields] == ["username", "password"]
        assert svc2.trusted_credential_recipient is True
        assert svc2.trusted_confirmed_by == "admin"

        tools2 = asyncio.run(app2.state.store.list_tools("ticm"))
        pt2 = next((t for t in tools2 if "portfolio_summary" in t.name), None)
        assert pt2 is not None
        assert pt2.risk_level == ToolRiskLevel.L1
        assert pt2.requires_credentials is True

