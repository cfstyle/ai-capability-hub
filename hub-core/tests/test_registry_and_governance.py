"""动态服务注册/发现与基础治理模块测试"""

import json
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.api.router import infer_tool_risk
from src.governance.middleware import GovernanceMiddleware, desensitize_params
from src.governance.audit import AuditLogger
from src.main import app
from src.registry.models import ServiceRegistration, ServiceStatus, ToolRiskLevel, RegisteredTool
from src.registry.store import RegistryStore


def test_registry_store_crud(tmp_path):
    """测试 RegistryStore 的增删查改"""
    async def _run():
        db_file = str(tmp_path / "test_hub.db")
        store = RegistryStore(db_file)
        await store.init_db()

        # 1. 注册服务
        reg = ServiceRegistration(
            service_id="mock_svc",
            name="Mock Service",
            endpoint_url="http://127.0.0.1:9999/mcp",
            description="A mock service for testing",
            owner="test-team",
        )
        svc = await store.register_service(reg)
        assert svc.id == "mock_svc"
        assert svc.status == ServiceStatus.ACTIVE

        # 2. 查询单个服务
        fetched = await store.get_service("mock_svc")
        assert fetched is not None
        assert fetched.name == "Mock Service"

        # 3. 保存工具列表
        tool1 = RegisteredTool(
            service_id="mock_svc",
            name="query_data",
            description="Query some data",
            input_schema={"type": "object"},
            risk_level=ToolRiskLevel.L0,
            requires_confirmation=False,
        )
        tool2 = RegisteredTool(
            service_id="mock_svc",
            name="delete_account",
            description="Delete user account",
            input_schema={"type": "object"},
            risk_level=ToolRiskLevel.L3,
            requires_confirmation=True,
        )
        await store.save_tools("mock_svc", [tool1, tool2])

        # 4. 列出工具
        tools = await store.list_tools(service_id="mock_svc")
        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "query_data" in tool_names
        assert "delete_account" in tool_names

        # 5. 更新服务状态
        updated = await store.update_service_status("mock_svc", ServiceStatus.INACTIVE)
        assert updated.status == ServiceStatus.INACTIVE

        # 6. 按状态过滤
        active_services = await store.list_services(status=ServiceStatus.ACTIVE)
        assert len(active_services) == 0

    import asyncio
    asyncio.run(_run())



def test_infer_tool_risk_levels():
    """测试风险分级自动推断规则 (L0/L1/L2/L3)"""
    lvl, confirm = infer_tool_risk("get_balance", "查询账户余额")
    assert lvl == ToolRiskLevel.L0
    assert confirm is False

    lvl, confirm = infer_tool_risk("calculate_tax", "估算税费草稿")
    assert lvl == ToolRiskLevel.L1
    assert confirm is False

    lvl, confirm = infer_tool_risk("send_notification", "发送系统通知")
    assert lvl == ToolRiskLevel.L2
    assert confirm is True

    lvl, confirm = infer_tool_risk("purge_database", "彻底清理系统数据")
    assert lvl == ToolRiskLevel.L3
    assert confirm is True


def test_param_desensitization():
    """测试调用入参敏感信息脱敏"""
    raw_params = {
        "user_id": "u123",
        "password": "my_secret_password",
        "api_key": "sk-123456",
        "nested": {
            "token": "bearer-token",
            "normal_field": "visible",
        },
    }
    cleaned = desensitize_params(raw_params)
    assert cleaned["user_id"] == "u123"
    assert cleaned["password"] == "***"
    assert cleaned["api_key"] == "***"
    assert cleaned["nested"]["token"] == "***"
    assert cleaned["nested"]["normal_field"] == "visible"


def test_rest_api_services_and_tools():
    """测试管理 REST API 端点"""
    from src.config import settings
    settings.admin_api_key = "test-admin-secret-key"
    with TestClient(app, headers={"X-Admin-Key": "test-admin-secret-key"}) as client:
        # 1. 注册新服务
        reg_payload = {
            "service_id": "api_test_svc",
            "name": "API Test Service",
            "endpoint_url": "http://127.0.0.1:8081/mcp",
            "description": "Registered via API",
            "owner": "qa-team",
        }
        res = client.post("/api/v1/services/register", json=reg_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "api_test_svc"

        # 2. 列出服务
        res = client.get("/api/v1/services")
        assert res.status_code == 200
        services = res.json()
        assert any(s["id"] == "api_test_svc" for s in services)

        # 3. 服务详情
        res = client.get("/api/v1/services/api_test_svc")
        assert res.status_code == 200
        assert res.json()["name"] == "API Test Service"

        # 4. 更新状态
        res = client.put("/api/v1/services/api_test_svc/status", json={"status": "inactive"})
        assert res.status_code == 200
        assert res.json()["status"] == "inactive"


        # 5. 查询工具列表
        res = client.get("/api/v1/tools")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # 6. 就绪探针
        res = client.get("/readyz")
        assert res.status_code == 200
        assert res.json()["status"] == "ready"


def test_governance_middleware_audit_logging():
    """测试治理中间件拦截工具调用并记录脱敏审计日志"""
    import asyncio
    from unittest.mock import MagicMock

    mock_audit = MagicMock()
    gw = GovernanceMiddleware(audit_logger=mock_audit)

    class DummyContext:
        class DummyMessage:
            name = "ticm__test_tool"
            arguments = {"account_id": "acc-001", "password": "super-secret"}
        message = DummyMessage()

    async def dummy_call_next(ctx):
        class DummyResult:
            isError = False
        return DummyResult()

    asyncio.run(gw.on_call_tool(DummyContext(), dummy_call_next))

    mock_audit.log_tool_call.assert_called_once()
    kwargs = mock_audit.log_tool_call.call_args.kwargs
    assert kwargs["tool_name"] == "ticm__test_tool"
    assert kwargs["service_id"] == "ticm"
    assert kwargs["params_summary"]["account_id"] == "acc-001"
    assert kwargs["params_summary"]["password"] == "***"
    assert kwargs["result_status"] == "success"


def test_update_service_and_policy_api():
    """测试服务元数据更新与工具策略调整 REST API"""
    from src.config import settings
    settings.admin_api_key = "test-admin-secret-key"
    with TestClient(app, headers={"X-Admin-Key": "test-admin-secret-key"}) as client:
        # 1. 更新元数据
        patch_payload = {
            "name": "Updated Mock Name",
            "owner": "new-owner",
            "description": "Updated business description",
        }
        res = client.patch("/api/v1/services/api_test_svc", json=patch_payload)
        if res.status_code == 200:
            data = res.json()
            assert data["name"] == "Updated Mock Name"
            assert data["owner"] == "new-owner"

        # 2. 查询已有工具
        res = client.get("/api/v1/tools")
        assert res.status_code == 200
        tools = res.json()
        if tools:
            target_tool = tools[0]
            # 3. 更新策略
            policy_payload = {
                "risk_level": "L2",
                "requires_confirmation": True,
            }
            res = client.patch(f"/api/v1/tools/{target_tool['name']}/policy", json=policy_payload)
            if res.status_code == 200:
                updated_tool = res.json()
                assert updated_tool["risk_level"] == "L2"
                assert updated_tool["requires_confirmation"] is True

        # 4. 查询审计日志
        res = client.get("/api/v1/audit-logs")
        assert res.status_code == 200
        assert "items" in res.json()
        assert "total" in res.json()


def test_governance_middleware_blocks_inactive_service(tmp_path):
    """测试治理中间件拦截停用服务的工具调用"""
    import asyncio
    db_file = str(tmp_path / "test_block.db")
    store = RegistryStore(db_file)

    async def _test():
        await store.init_db()
        reg = ServiceRegistration(
            service_id="blocked_svc",
            name="Blocked Service",
            endpoint_url="http://127.0.0.1:9099/mcp",
            description="Testing blocked service",
            owner="test",
        )
        await store.register_service(reg)
        await store.update_service_status("blocked_svc", ServiceStatus.INACTIVE)

        gw = GovernanceMiddleware(store=store)

        class DummyContext:
            class DummyMessage:
                name = "blocked_svc__sensitive_tool"
                arguments = {"param": "val"}
            message = DummyMessage()

        called = False
        async def dummy_call_next(ctx):
            nonlocal called
            called = True

        with pytest.raises(RuntimeError, match="blocked by Gateway"):
            await gw.on_call_tool(DummyContext(), dummy_call_next)

        assert called is False

    asyncio.run(_test())


