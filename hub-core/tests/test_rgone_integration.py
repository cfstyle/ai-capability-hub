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
