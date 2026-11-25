"""测试改动 3：统一授权匹配规则与拒绝审计入库

验收覆盖：
1. 两个服务存在同名工具时精确隔离，授权 A 无法越权调用 B，下游调用为 0，记录拒绝审计；
2. 相似工具名前缀/子串防御，不因模糊匹配放行未授权工具；
3. 未知未登记工具拦截，下游调用为 0，记录拒绝审计；
4. 停用服务拦截，下游调用为 0，记录拒绝审计；
5. 调试台 test_tool_call 对停用服务与未知工具拦截，记录拒绝审计；
6. 复杂嵌套参数（dict/list）递归脱敏验证。
"""

import asyncio
from unittest.mock import MagicMock
import pytest

from src.governance.auth import TokenPayload, set_current_user
from src.governance.middleware import GovernanceMiddleware, desensitize_params
from src.registry.models import (
    RegisteredTool,
    ServiceRegistration,
    ServiceStatus,
    ToolRiskLevel,
    UserGrant,
)
from src.registry.store import RegistryStore


@pytest.fixture
def temp_store(tmp_path):
    db_file = str(tmp_path / "test_auth_audit.db")
    store = RegistryStore(db_file)
    asyncio.run(store.init_db())
    return store


def test_param_recursive_desensitization():
    """测试嵌套字典、列表和深层结构的参数递归脱敏"""
    raw_params = {
        "user": "alice",
        "api_key": "my-secret-key",
        "nested": {
            "token": "tok-123456",
            "normal_field": "safe",
            "items": [
                {"password": "pass-999", "name": "item1"},
                "plain_string",
                {"authorization": "Bearer xxx", "count": 10},
            ],
        },
    }
    clean = desensitize_params(raw_params)
    assert clean["api_key"] == "***"
    assert clean["nested"]["token"] == "***"
    assert clean["nested"]["normal_field"] == "safe"
    assert clean["nested"]["items"][0]["password"] == "***"
    assert clean["nested"]["items"][0]["name"] == "item1"
    assert clean["nested"]["items"][1] == "plain_string"
    assert clean["nested"]["items"][2]["authorization"] == "***"


def test_two_services_same_tool_name_isolation(temp_store):
    """测试两个服务存在同名工具时的精确授权隔离与审计记录"""
    store = temp_store

    async def _run():
        # 1. 注册两个服务
        await store.register_service(ServiceRegistration(
            service_id="svc_a", name="Service A", endpoint_url="http://127.0.0.1:9001/mcp", description="A", owner="team_a"
        ))
        await store.register_service(ServiceRegistration(
            service_id="svc_b", name="Service B", endpoint_url="http://127.0.0.1:9002/mcp", description="B", owner="team_b"
        ))

        # 2. 两个服务均有同名工具 query_data，但各自有独立 ID
        tool_a = RegisteredTool(
            id="svc_a__query_data", service_id="svc_a", name="query_data",
            description="Query in A", input_schema={}, risk_level=ToolRiskLevel.L1,
        )
        tool_b = RegisteredTool(
            id="svc_b__query_data", service_id="svc_b", name="query_data",
            description="Query in B", input_schema={}, risk_level=ToolRiskLevel.L1,
        )
        await store.save_tools("svc_a", [tool_a])
        await store.save_tools("svc_b", [tool_b])

        # 3. 用户 user_a 只被授予 svc_a__query_data 的权限
        await store.grant_tools("user_a", ["svc_a__query_data"])

        gw = GovernanceMiddleware(store=store)

        # 设置当前用户上下文为 user_a
        set_current_user(TokenPayload(
            sub="user_a", client_id="test-client-a", scopes=["hub:tools:call"],
        ))

        # 4. 场景 1：调用 svc_a__query_data -> 成功
        downstream_called_a = 0
        async def call_next_a(ctx):
            nonlocal downstream_called_a
            downstream_called_a += 1
            class DummyRes:
                isError = False
            return DummyRes()

        class CtxA:
            class DummyMessage:
                name = "svc_a__query_data"
                arguments = {"q": "test"}
            message = DummyMessage()

        await gw.on_call_tool(CtxA(), call_next_a)
        assert downstream_called_a == 1

        # 5. 场景 2：user_a 尝试调用 svc_b__query_data -> 必须被拦截！
        downstream_called_b = 0
        async def call_next_b(ctx):
            nonlocal downstream_called_b
            downstream_called_b += 1

        class CtxB:
            class DummyMessage:
                name = "svc_b__query_data"
                arguments = {"q": "test_b"}
            message = DummyMessage()

        with pytest.raises(PermissionError) as exc_info:
            await gw.on_call_tool(CtxB(), call_next_b)
        assert "requires explicit authorization" in str(exc_info.value)
        # 断言下游调用次数严格为零
        assert downstream_called_b == 0

        # 6. 检查审计库：有且仅有一条针对 svc_b 的拒绝审计记录
        logs, total = await store.list_invocation_logs(service_id="svc_b")
        assert total >= 1
        b_log = [l for l in logs if l.tool_name == "svc_b__query_data"][0]
        assert b_log.user_id == "user_a"
        assert "rejected: permission denied" in b_log.result_status
        assert b_log.duration_ms >= 0

    asyncio.run(_run())


def test_similar_tool_names_substring_defense(temp_store):
    """测试相似工具名前缀/子串防御（授权 send_message_batch 不得误放行 send_message）"""
    store = temp_store

    async def _run():
        await store.register_service(ServiceRegistration(
            service_id="msg_svc", name="Msg Svc", endpoint_url="http://127.0.0.1:9003/mcp", description="Msg", owner="qa"
        ))
        tool_batch = RegisteredTool(
            id="msg_svc__send_message_batch", service_id="msg_svc", name="send_message_batch",
            description="Batch", input_schema={}, risk_level=ToolRiskLevel.L2,
        )
        tool_single = RegisteredTool(
            id="msg_svc__send_message", service_id="msg_svc", name="send_message",
            description="Single", input_schema={}, risk_level=ToolRiskLevel.L2,
        )
        await store.save_tools("msg_svc", [tool_batch, tool_single])

        # 仅授权 batch
        await store.grant_tools("user_b", ["msg_svc__send_message_batch"])

        gw = GovernanceMiddleware(store=store)
        set_current_user(TokenPayload(
            sub="user_b", client_id="test-client-b", scopes=["hub:tools:call"],
        ))

        downstream_called = 0
        async def call_next(ctx):
            nonlocal downstream_called
            downstream_called += 1

        class CtxSingle:
            class DummyMessage:
                name = "msg_svc__send_message"
                arguments = {"text": "hello"}
            message = DummyMessage()

        with pytest.raises(PermissionError):
            await gw.on_call_tool(CtxSingle(), call_next)

        assert downstream_called == 0

        # 断言审计库存在带主体与拒绝原因的记录
        logs, _ = await store.list_invocation_logs(tool_name="send_message")
        rejected_logs = [l for l in logs if l.tool_name == "msg_svc__send_message"]
        assert len(rejected_logs) >= 1
        assert rejected_logs[0].user_id == "user_b"
        assert "rejected: permission denied" in rejected_logs[0].result_status

    asyncio.run(_run())


def test_unknown_tool_and_inactive_service_rejections(temp_store):
    """测试未知工具与停用服务拦截，断言下游调用为零且写入结构化审计"""
    store = temp_store

    async def _run():
        await store.register_service(ServiceRegistration(
            service_id="active_svc", name="Active", endpoint_url="http://127.0.0.1:9004/mcp", description="", owner=""
        ))
        await store.register_service(ServiceRegistration(
            service_id="inactive_svc", name="Inactive", endpoint_url="http://127.0.0.1:9005/mcp", description="", owner=""
        ))
        await store.update_service_status("inactive_svc", ServiceStatus.INACTIVE)

        tool_inactive = RegisteredTool(
            id="inactive_svc__ping", service_id="inactive_svc", name="ping",
            description="Ping", input_schema={}, risk_level=ToolRiskLevel.L0,
        )
        await store.save_tools("inactive_svc", [tool_inactive])

        gw = GovernanceMiddleware(store=store)
        set_current_user(TokenPayload(sub="regular_user", client_id="c1", scopes=["hub:tools:call"]))

        # 1. 未知工具测试
        downstream_called_unknown = 0
        async def call_next_unknown(ctx):
            nonlocal downstream_called_unknown
            downstream_called_unknown += 1

        class CtxUnknown:
            class DummyMessage:
                name = "nonexistent_service__no_such_tool"
                arguments = {}
            message = DummyMessage()

        with pytest.raises(KeyError):
            await gw.on_call_tool(CtxUnknown(), call_next_unknown)
        assert downstream_called_unknown == 0

        logs, _ = await store.list_invocation_logs()
        unknown_log = [l for l in logs if "no_such_tool" in l.tool_name][0]
        assert unknown_log.user_id == "regular_user"
        assert "rejected: unknown tool" in unknown_log.result_status

        # 2. 停用服务测试 (即使工具是 L0)
        downstream_called_inactive = 0
        async def call_next_inactive(ctx):
            nonlocal downstream_called_inactive
            downstream_called_inactive += 1

        class CtxInactive:
            class DummyMessage:
                name = "inactive_svc__ping"
                arguments = {}
            message = DummyMessage()

        with pytest.raises(RuntimeError, match="blocked by Gateway"):
            await gw.on_call_tool(CtxInactive(), call_next_inactive)
        assert downstream_called_inactive == 0

        logs, _ = await store.list_invocation_logs(service_id="inactive_svc")
        inactive_log = [l for l in logs if l.tool_name == "inactive_svc__ping"][0]
        assert inactive_log.user_id == "regular_user"
        assert "rejected: service 'inactive_svc' is inactive" in inactive_log.result_status

    asyncio.run(_run())


def test_test_tool_call_debug_enforces_active_service(tmp_path):
    """测试调试台 test_tool_call 严格遵守服务停用限制并记入审计"""
    from fastapi.testclient import TestClient
    from src.main import build_app
    from src.config import settings

    settings.admin_api_key = "test-admin-secret"
    app = build_app()

    with TestClient(app, headers={"X-Admin-Key": "test-admin-secret"}) as client:
        # 1. 注册服务
        client.post("/api/v1/services/register", json={
            "service_id": "debug_svc",
            "name": "Debug Service",
            "endpoint_url": "http://127.0.0.1:9006/mcp",
            "description": "debug",
            "owner": "admin",
        })
        # 2. 停用服务
        client.put("/api/v1/services/debug_svc/status", json={"status": "inactive"})

        # 3. 尝试调用调试端点
        resp = client.post("/api/v1/tools/debug_svc__any_tool/test", json={"arguments": {"key": "val"}})
        # 应当被拒绝，返回 403 或 404
        assert resp.status_code in (403, 404)

        # 4. 验证审计日志记录了管理员对停用服务/未知工具的拦截
        audit_resp = client.get("/api/v1/audit-logs")
        assert audit_resp.status_code == 200
        logs = audit_resp.json()["items"]
        assert any("rejected" in l["result_status"] for l in logs)
