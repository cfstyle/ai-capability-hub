"""公开能力门户 (Capability Portal) API 测试

覆盖：
1. 匿名免登录访问校验（不带任何 Token / API Key）
2. 数据脱敏检查（严禁暴露真实 upstream endpoint_url 与 owner 内部隐私）
3. 服务状态安全边界（非 active 服务严禁在卡片列表中暴露，请求返回 404）
4. 真实调用统计与日志驱动验证（调用日志写入后统计真实递增，无数据时展示 0）
5. 统一 MCP Gateway 对接信息推导与认证说明
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.registry.models import (
    RegisteredTool,
    ServiceRegistration,
    ServiceStatus,
    ToolRiskLevel,
)
from src.registry.store import RegistryStore


@pytest.fixture
def test_client():
    """构建测试客户端并获取应用内的 store"""
    with TestClient(app) as client:
        store = app.state.store
        yield client, store


def test_portal_anonymous_access_overview(test_client):
    """测试完全免登访问 /api/v1/portal/overview"""
    client, store = test_client
    # 不传任何 X-API-Key 或 Authorization
    resp = client.get("/api/v1/portal/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "services_count" in data
    assert "tools_count" in data
    assert "total_calls" in data
    assert "daily_trends" in data
    assert len(data["daily_trends"]) == 7


def test_portal_desensitization_and_filtering(test_client):
    """测试能力列表的严格脱敏与状态隔离边界"""
    client, store = test_client

    import asyncio

    async def _setup():
        # 1. 注册 active 服务
        svc_active = ServiceRegistration(
            service_id="knowledge_qa",
            name="企业知识问答服务",
            endpoint_url="http://192.168.1.100:8081/mcp",
            description="面向企业内部文档的智能检索问答",
            owner="infra-secret-user",
            category="知识检索",
            auth_mode="platform_sso",
            auth_label="Hub 统一认证",
        )
        await store.register_service(svc_active)

        # 2. 注册已停用的内部服务
        svc_inactive = ServiceRegistration(
            service_id="internal_draft",
            name="内部未发布测试服务",
            endpoint_url="http://127.0.0.1:9999/mcp",
            description="内部草稿，不应对外暴露",
            owner="admin-private",
        )
        await store.register_service(svc_inactive)
        await store.update_service_status("internal_draft", ServiceStatus.INACTIVE)

        # 3. 添加工具
        tool = RegisteredTool(
            service_id="knowledge_qa",
            name="search_docs",
            description="检索内部知识库文档",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            risk_level=ToolRiskLevel.L0,
        )
        await store.save_tools("knowledge_qa", [tool])

    asyncio.run(_setup())

    # 匿名拉取公开能力列表
    resp = client.get("/api/v1/portal/capabilities")
    assert resp.status_code == 200
    items = resp.json()

    # 1. 过滤校验：仅 active 服务展示，inactive 服务被完全剔除
    service_ids = [item["id"] for item in items]
    assert "knowledge_qa" in service_ids
    assert "internal_draft" not in service_ids

    # 2. 脱敏校验：严禁包含 endpoint_url 和 owner
    for item in items:
        assert "endpoint_url" not in item
        assert "owner" not in item
        # 文本中不得泄露上游内网 IP 端口
        content_str = str(item)
        assert "192.168.1.100" not in content_str
        assert "127.0.0.1" not in content_str
        assert "infra-secret-user" not in content_str

    # 3. 详情接口安全隔离测试
    # 请求 active 服务详情应成功
    detail_resp = client.get("/api/v1/portal/capabilities/knowledge_qa")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["name"] == "企业知识问答服务"
    assert "endpoint_url" not in detail
    assert "owner" not in detail
    assert "gateway_url" in detail
    assert detail["protocol"] == "Streamable HTTP"
    assert detail["auth_label"] == "Hub 统一认证"
    assert len(detail["tools"]) == 1
    assert detail["tools"][0]["name"] == "search_docs"

    # 请求 inactive 服务详情应直接 404，不向外界泄露存在性
    inactive_resp = client.get("/api/v1/portal/capabilities/internal_draft")
    assert inactive_resp.status_code == 404


def test_portal_real_statistics_increase(test_client):
    """测试真实调用统计驱动与日志递增，严禁假数据"""
    client, store = test_client
    import uuid
    import asyncio

    unique_svc_id = f"stat_{uuid.uuid4().hex[:6]}"

    async def _setup():
        svc = ServiceRegistration(
            service_id=unique_svc_id,
            name="统计演示服务",
            endpoint_url="http://mock:8080/mcp",
            description="用于测试调用量统计",
            owner="test",
        )
        await store.register_service(svc)

    asyncio.run(_setup())

    # 初始检查
    resp1 = client.get("/api/v1/portal/overview")
    assert resp1.status_code == 200
    initial_calls = resp1.json()["total_calls"]

    # 模拟真实写入 2 条调用日志
    async def _log_calls():
        await store.save_invocation_log({
            "service_id": unique_svc_id,
            "tool_name": f"{unique_svc_id}__test_tool",
            "result_status": "success",
            "duration_ms": 12.5,
        })
        await store.save_invocation_log({
            "service_id": unique_svc_id,
            "tool_name": f"{unique_svc_id}__test_tool",
            "result_status": "success",
            "duration_ms": 15.0,
        })

    asyncio.run(_log_calls())

    # 再次刷新概览：total_calls 真实递增 2
    resp2 = client.get("/api/v1/portal/overview")
    assert resp2.status_code == 200
    assert resp2.json()["total_calls"] == initial_calls + 2

    # 检查能力列表中的调用次数
    caps_resp = client.get("/api/v1/portal/capabilities")
    assert caps_resp.status_code == 200
    items = caps_resp.json()
    stat_item = next(it for it in items if it["id"] == unique_svc_id)
    assert stat_item["call_count"] == 2
