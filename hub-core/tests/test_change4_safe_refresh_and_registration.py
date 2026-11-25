"""测试改动 4：把注册和刷新改为“发现成功后再提交”

验收覆盖：
1. 先把工具风险人工调高，再刷新，断言风险级别与确认策略不回落；
2. 先保存有效快照，再模拟发现超时/断连，断言工具 ID、数量、Schema 和授权均完好保留；
3. 注册时非法 URL 协议安全拦截。
"""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import build_app
from src.config import settings
from src.registry.models import (
    RegisteredTool,
    ServiceRegistration,
    ToolRiskLevel,
    UserGrant,
)
from src.registry.store import RegistryStore


@pytest.fixture
def test_client():
    settings.admin_api_key = "test-change4-secret"
    app = build_app()
    with TestClient(app, headers={"X-Admin-Key": "test-change4-secret"}) as c:
        yield c


def test_invalid_url_scheme_rejected(test_client: TestClient):
    """测试非法或非 http/https 协议地址在首次连接前被拒绝"""
    resp = test_client.post("/api/v1/services/register", json={
        "service_id": "bad_scheme_svc",
        "name": "Bad Scheme",
        "endpoint_url": "ftp://127.0.0.1:21/mcp",
        "description": "ftp",
        "owner": "admin",
    })
    assert resp.status_code == 400
    assert "Only 'http' and 'https' are allowed" in resp.json()["detail"]


def test_tool_risk_preserved_after_refresh(tmp_path):
    """核心回归测试 1：先把工具风险人工调高，再刷新，断言风险不回落"""
    db_file = str(tmp_path / "test_risk_preserve.db")
    store = RegistryStore(db_file)

    async def _run():
        await store.init_db()
        # 1. 初始入库服务与一个推断为 L0 的工具
        await store.register_service(ServiceRegistration(
            service_id="risk_test_svc",
            name="Risk Test Service",
            endpoint_url="http://127.0.0.1:9091/mcp",
            description="Testing risk preservation",
            owner="admin",
        ))
        initial_tool = RegisteredTool(
            id="risk_test_svc__query_info",
            service_id="risk_test_svc",
            name="query_info",
            description="Query general info",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
            risk_level=ToolRiskLevel.L0,
            requires_confirmation=False,
        )
        await store.save_tools("risk_test_svc", [initial_tool])

        # 2. 管理员人工将工具风险调高至 L2，并开启人工确认
        updated = await store.update_tool_policy(
            tool_id="risk_test_svc__query_info",
            risk_level=ToolRiskLevel.L2,
            requires_confirmation=True,
        )
        assert updated.risk_level == ToolRiskLevel.L2
        assert updated.requires_confirmation is True

        # 3. 模拟一次新发现返回同名工具（上游返回推断为 L0 的新快照）
        new_discovered_tool = RegisteredTool(
            id="risk_test_svc__query_info",
            service_id="risk_test_svc",
            name="query_info",
            description="Query general info updated upstream",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}, "limit": {"type": "integer"}}},
            risk_level=ToolRiskLevel.L0,  # 上游自动推断为 L0
            requires_confirmation=False,
        )

        # 4. 执行刷新保存（开启 preserve_policies=True）
        await store.save_tools("risk_test_svc", [new_discovered_tool], preserve_policies=True)

        # 5. 断言：工具风险级别依然保持 L2，人工确认要求依然保持 True，未回落！同时 Schema 成功更新
        tools = await store.list_tools("risk_test_svc")
        assert len(tools) == 1
        t = tools[0]
        assert t.name == "query_info"
        assert t.risk_level == ToolRiskLevel.L2  # 成功保留 L2！
        assert t.requires_confirmation is True   # 成功保留人工确认！
        assert "limit" in t.input_schema.get("properties", {})  # 新 Schema 正常生效

    asyncio.run(_run())


def test_snapshot_preserved_on_discovery_timeout(test_client: TestClient):
    """核心回归测试 2：先保存有效快照，再模拟发现超时，断言工具 ID、数量、Schema 和授权均完好保留"""
    # 1. 注册服务并手动注入初始工具与授权
    reg_resp = test_client.post("/api/v1/services/register", json={
        "service_id": "timeout_svc",
        "name": "Timeout Service",
        "endpoint_url": "http://127.0.0.1:9092/mcp",
        "description": "test timeout",
        "owner": "admin",
    })
    assert reg_resp.status_code == 200

    app = test_client.app
    store: RegistryStore = app.state.store

    async def _setup_data():
        tool_1 = RegisteredTool(
            id="timeout_svc__export_excel",
            service_id="timeout_svc",
            name="export_excel",
            description="Export data to Excel",
            input_schema={"properties": {"file_name": {"type": "string"}}},
            risk_level=ToolRiskLevel.L1,
            requires_confirmation=False,
        )
        tool_2 = RegisteredTool(
            id="timeout_svc__delete_backup",
            service_id="timeout_svc",
            name="delete_backup",
            description="Delete obsolete backup",
            input_schema={"properties": {"backup_id": {"type": "string"}}},
            risk_level=ToolRiskLevel.L3,
            requires_confirmation=True,
        )
        await store.save_tools("timeout_svc", [tool_1, tool_2])
        await store.grant_tools("analyst_01", ["timeout_svc__export_excel"])

    asyncio.run(_setup_data())

    # 验证初始状态：2 个工具，1 个授权
    initial_tools = asyncio.run(store.list_tools("timeout_svc"))
    assert len(initial_tools) == 2
    initial_grants = asyncio.run(store.get_user_granted_tool_ids("analyst_01"))
    assert "timeout_svc__export_excel" in initial_grants

    # 2. 模拟下游工具发现抛出网络超时或协议异常
    with patch("src.api.router.discover_tools", side_effect=RuntimeError("Connection timed out after 5000ms")):
        refresh_resp = test_client.post("/api/v1/services/timeout_svc/refresh")
        # 必须返回明确的 502 错误，向管理员报告上游异常
        assert refresh_resp.status_code == 502
        assert "Existing tools and policies have been preserved" in refresh_resp.json()["detail"]

    # 3. 核心断言：断连后工具数量、ID、Schema、风险级别和授权记录 100% 完好保留！绝未被清空！
    after_tools = asyncio.run(store.list_tools("timeout_svc"))
    assert len(after_tools) == 2
    tool_map = {t.name: t for t in after_tools}
    assert "export_excel" in tool_map
    assert "delete_backup" in tool_map
    assert tool_map["export_excel"].risk_level == ToolRiskLevel.L1
    assert tool_map["delete_backup"].risk_level == ToolRiskLevel.L3
    assert "file_name" in tool_map["export_excel"].input_schema.get("properties", {})

    after_grants = asyncio.run(store.get_user_granted_tool_ids("analyst_01"))
    assert "timeout_svc__export_excel" in after_grants
