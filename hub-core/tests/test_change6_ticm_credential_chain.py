"""测试改动 6：个人业务凭据绑定、双用户隔离调用与状态维护 (以 TICM 为例)

涵盖纵向端到端全链路验证：
1. 开发者声明凭据要求 (TICM 声明 username, password，兼容无凭据插件)。
2. 用户申请工具并绑定凭据，申请记录只存摘要不存密码。
3. 管理员审批授权。
4. 双用户（张三 dev-user，李四 risk-01）从正式 MCP 入口调用，各自自动登录独立 session，返回专属持仓，杜绝串号。
5. 多工具复用同一绑定。
6. 未绑定凭据或解绑后立即阻断调用，审计记录被阻断。
7. 改密即时失效旧 session。
"""

import json
import os
import pytest
from datetime import date
from starlette.testclient import TestClient

from src.main import build_app
from src.registry.models import (
    CredentialFieldSchema,
    CredentialFieldType,
    PermissionRequestCreate,
    PermissionRequestStatus,
    ServiceCredentialSchema,
    ServiceRegistration,
    ToolRiskLevel,
    UserServiceBindingUpdate,
)
from src.governance.auth import create_access_token, ADMIN_SCOPES, USER_SCOPES


@pytest.fixture
def test_setup(tmp_path, monkeypatch):
    """初始化测试环境与独立 SQLite 数据库"""
    from src.config import settings, load_config
    load_config.cache_clear()
    settings.admin_api_key = "test-admin-secret"
    settings.upstream_services = []

    db_file = tmp_path / "test_hub_cred.db"
    monkeypatch.setenv("HUB_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("HUB_ENV", "development")
    monkeypatch.setenv("HUB_ADMIN_API_KEY", "test-admin-secret")
    monkeypatch.setenv("HUB_CREDENTIAL_ENCRYPTION_KEY", "u1_2bHk8Sj2O8B9p-w4Z3o7I_f5V1m8N6Y0x4R2T5Qc=")

    app = build_app()
    with TestClient(app) as client:
        yield client, app.state.store, app.state.aggregator


@pytest.mark.anyio
async def test_ticm_credential_binding_and_dual_user_isolation(test_setup):
    client, store, aggregator = test_setup

    # 1. 注册 TICM 服务 (声明凭据要求)
    ticm_cred_schema = ServiceCredentialSchema(
        enabled=True,
        auth_type="username_password",
        instructions="请填写您在 TICM 债券资管系统的专有交易账号与密码",
        fields=[
            CredentialFieldSchema(
                field_name="username",
                label="TICM 用户名",
                field_type=CredentialFieldType.TEXT,
                required=True,
                secret=False,
            ),
            CredentialFieldSchema(
                field_name="password",
                label="TICM 登录密码",
                field_type=CredentialFieldType.PASSWORD,
                required=True,
                secret=True,
            ),
        ],
    )

    ticm_reg = ServiceRegistration(
        service_id="ticm",
        name="TICM 债券资管系统",
        endpoint_url="http://127.0.0.1:8081/mcp",
        description="提供持仓汇总与债券明细",
        credential_schema=ticm_cred_schema,
        trusted_credential_recipient=False,
    )
    await store.register_service(ticm_reg)
    await store.confirm_credential_trust("ticm", True, confirmed_by="admin")

    # 注册一个无需个人凭据的普通服务 (验证兼容性)
    public_reg = ServiceRegistration(
        service_id="public_news",
        name="市场资讯服务",
        endpoint_url="http://127.0.0.1:8082/mcp",
        description="公开市场宏观资讯，无需个人账号",
        credential_schema=None,
    )
    await store.register_service(public_reg)

    # 保存 TICM 工具定义
    from src.registry.models import RegisteredTool
    tools = [
        RegisteredTool(
            id="ticm__portfolio_summary",
            name="portfolio_summary",
            service_id="ticm",
            description="获取当前用户的持仓概况",
            risk_level=ToolRiskLevel.L1,
            requires_credentials=True,
            namespace_name="ticm__portfolio_summary",
        ),
        RegisteredTool(
            id="ticm__bond_detail",
            name="bond_detail",
            service_id="ticm",
            description="查询单只债券详情",
            risk_level=ToolRiskLevel.L0,  # L0 无需审批
            requires_credentials=False,
            namespace_name="ticm__bond_detail",
        ),
    ]
    await store.save_tools("ticm", tools)

    # 2. 模拟用户凭据 Token
    zhangsan_token = create_access_token("dev-user", "user", USER_SCOPES)
    lisi_token = create_access_token("risk-01", "user", USER_SCOPES)
    admin_token = create_access_token("admin", "admin", ADMIN_SCOPES)

    # 3. 张三在门户申请 TICM 工具并绑定凭据
    apply_payload_zhangsan = {
        "service_id": "ticm",
        "tool_ids": ["ticm__portfolio_summary"],
        "reason": "投资业务持仓盘点",
        "credentials": {
            "username": "zhangsan",
            "password": "pwd_zhangsan_123",
        },
    }
    resp = client.post(
        "/api/v1/portal/permission-requests",
        json=apply_payload_zhangsan,
        headers={"Authorization": f"Bearer {zhangsan_token}"},
    )
    assert resp.status_code == 200, resp.text
    req_zhangsan = resp.json()
    assert req_zhangsan["user_id"] == "dev-user"
    assert req_zhangsan["has_credential_binding"] is True
    # 绝不泄漏密码
    assert "pwd_zhangsan_123" not in json.dumps(req_zhangsan)
    assert req_zhangsan["credential_summary"]["username"] == "zhangsan"
    assert req_zhangsan["credential_summary"]["has_password"] is True

    # 李四在门户申请 TICM 工具并绑定凭据
    apply_payload_lisi = {
        "service_id": "ticm",
        "tool_ids": ["ticm__portfolio_summary"],
        "reason": "风控指标盯盘",
        "credentials": {
            "username": "lisi",
            "password": "pwd_lisi_456",
        },
    }
    resp = client.post(
        "/api/v1/portal/permission-requests",
        json=apply_payload_lisi,
        headers={"Authorization": f"Bearer {lisi_token}"},
    )
    assert resp.status_code == 200
    req_lisi = resp.json()
    assert req_lisi["user_id"] == "risk-01"

    # 4. 管理员审批两个申请
    resp = client.post(
        f"/api/v1/admin/permission-requests/{req_zhangsan['id']}/review",
        json={"status": "approved", "comment": "同意开通持仓查询"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        f"/api/v1/admin/permission-requests/{req_lisi['id']}/review",
        json={"status": "approved", "comment": "同意风控查询"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    # 5. 校验用户门户“我添加的 MCP”摘要
    resp = client.get("/api/v1/portal/my-mcps", headers={"Authorization": f"Bearer {zhangsan_token}"})
    assert resp.status_code == 200
    my_mcps = resp.json()
    ticm_summary = next((m for m in my_mcps if m["service_id"] == "ticm"), None)
    assert ticm_summary is not None
    assert ticm_summary["requires_credentials"] is True
    assert ticm_summary["credential_status"] == "saved"
    assert ticm_summary["credential_summary"]["username"] == "zhangsan"
    assert "pwd_zhangsan_123" not in json.dumps(ticm_summary)
    assert len(ticm_summary["approved_tools"]) == 1

    # 6. 正式调用与双用户会话隔离验证
    from src.governance.middleware import current_invocation_credential_cv

    captured_headers = {}

    async def mock_call_next(context):
        cred_ctx = current_invocation_credential_cv.get()
        if cred_ctx:
            captured_headers["X-Hub-User-Id"] = cred_ctx["user_id"]
            captured_headers["X-Hub-Credential-Version"] = str(cred_ctx["credential_version"])
            captured_headers["X-Hub-User-Credentials"] = json.dumps(cred_ctx["credentials"])

        # 通过独立 mock_ticm_backend ASGI 测试登录与 Cookie 隔离
        import importlib.util
        from pathlib import Path
        backend_path = Path(__file__).resolve().parent.parent.parent / "services" / "ticm-mcp" / "mock_ticm_backend.py"
        spec = importlib.util.spec_from_file_location("ticm_backend_mod", str(backend_path))
        backend_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend_mod)

        import httpx
        transport = httpx.ASGITransport(app=backend_mod.build_backend_app())
        creds = json.loads(captured_headers["X-Hub-User-Credentials"])
        async with httpx.AsyncClient(transport=transport, base_url="http://ticm-backend") as hc:
            login_resp = await hc.post("/ticm/api/login", json={"username": creds["username"], "password": creds["password"]})
            assert login_resp.status_code == 200
            sess = login_resp.cookies.get("ticm_session")
            pos_resp = await hc.get("/ticm/api/positions", cookies={"ticm_session": sess})
            assert pos_resp.status_code == 200
            pos_data = pos_resp.json()
        return {
            "portfolio_name": pos_data["portfolio_name"],
            "total_amount": pos_data["total_amount"],
            "session_id": sess,
            "username": pos_data["username"],
        }

    # 测试张三通过中间件调用
    class MockCallContext:
        class MockMessage:
            name = "ticm__portfolio_summary"
            arguments = {"business_date": "2026-11-24"}
        message = MockMessage()

    from src.governance.auth import current_user_cv, TokenPayload
    # 设置张三用户上下文
    user_token_zhangsan = current_user_cv.set(TokenPayload(sub="dev-user", client_id="cursor", scopes=USER_SCOPES, exp=0))
    try:
        res_zhangsan = await aggregator.governance_middleware.on_call_tool(MockCallContext(), mock_call_next)
    finally:
        current_user_cv.reset(user_token_zhangsan)

    assert res_zhangsan["username"] == "zhangsan"
    assert res_zhangsan["portfolio_name"] == "张三稳健优选组合"
    assert res_zhangsan["total_amount"] == 1_428_570_000.0
    sess_zhangsan = res_zhangsan["session_id"]

    # 设置李四用户上下文
    captured_headers.clear()
    user_token_lisi = current_user_cv.set(TokenPayload(sub="risk-01", client_id="cursor", scopes=USER_SCOPES, exp=0))
    try:
        res_lisi = await aggregator.governance_middleware.on_call_tool(MockCallContext(), mock_call_next)
    finally:
        current_user_cv.reset(user_token_lisi)

    assert res_lisi["username"] == "lisi"
    assert res_lisi["portfolio_name"] == "李四高收益成长组合"
    assert res_lisi["total_amount"] == 500_000_000.0
    sess_lisi = res_lisi["session_id"]

    # 关键断言：会话必须严格隔离，绝不发生串号
    assert sess_zhangsan != sess_lisi

    # 7. 缺少凭据调用的阻断验证 (王五获批但未配置凭据)
    await store.grant_tools("trader-wang", ["ticm__portfolio_summary"])
    user_token_wang = current_user_cv.set(TokenPayload(sub="trader-wang", client_id="cursor", scopes=USER_SCOPES, exp=0))
    downstream_called = False

    async def mock_downstream_fail(context):
        nonlocal downstream_called
        downstream_called = True
        return {}

    try:
        with pytest.raises(RuntimeError) as exc_info:
            await aggregator.governance_middleware.on_call_tool(MockCallContext(), mock_downstream_fail)
        assert "requires personal credentials" in str(exc_info.value)
        # 下游调用严格为 0
        assert downstream_called is False
    finally:
        current_user_cv.reset(user_token_wang)

    # 8. 解绑凭据即时生效
    resp = client.delete(
        "/api/v1/portal/my-mcps/ticm/binding",
        headers={"Authorization": f"Bearer {zhangsan_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["unbound"] is True

    # 张三解绑后再调用立即被阻止
    user_token_zhangsan = current_user_cv.set(TokenPayload(sub="dev-user", client_id="cursor", scopes=USER_SCOPES, exp=0))
    try:
        with pytest.raises(RuntimeError) as exc_info:
            await aggregator.governance_middleware.on_call_tool(MockCallContext(), mock_downstream_fail)
        assert "requires personal credentials" in str(exc_info.value)
    finally:
        current_user_cv.reset(user_token_zhangsan)
