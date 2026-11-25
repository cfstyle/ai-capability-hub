"""AI Capability Hub - Portal 核心功能与安全边界完整验收自检脚本"""

import json
from fastapi.testclient import TestClient

from src.main import app
from src.registry.models import (
    RegisteredTool,
    ServiceRegistration,
    ServiceStatus,
    ToolRiskLevel,
)
from src.registry.store import RegistryStore

def run_self_check():
    print("=" * 70)
    print("开始执行 Capability Portal 核心功能与安全红线完整验证")
    print("=" * 70)

    with TestClient(app) as client:
        store: RegistryStore = app.state.store
        # 模拟生产/部署环境开启了 HUB_ADMIN_API_KEY 鉴权
        app.state.config.admin_api_key = "dev-admin-key"
        import asyncio

        # --- 1. 匿名访问与管理鉴权边界验证 ---
        print("\n[测试 1] 匿名访问与管理端鉴权边界验证...")
        # 1.1 匿名访问概览接口
        resp_overview = client.get("/api/v1/portal/overview")
        assert resp_overview.status_code == 200, f"概览接口应允许免登访问，实际状态码: {resp_overview.status_code}"
        print("  ✓ GET /api/v1/portal/overview 匿名免登访问通过 (HTTP 200)")

        # 1.2 匿名访问公开能力列表
        resp_caps = client.get("/api/v1/portal/capabilities")
        assert resp_caps.status_code == 200, f"能力列表应允许免登访问，实际状态码: {resp_caps.status_code}"
        print("  ✓ GET /api/v1/portal/capabilities 匿名免登访问通过 (HTTP 200)")

        # 1.3 匿名访问管理接口应被拦截 (ADR-009)
        resp_admin_anon = client.get("/api/v1/services")
        assert resp_admin_anon.status_code == 401, f"未登录访问管理接口应拦截为 401，实际: {resp_admin_anon.status_code}"
        print("  ✓ GET /api/v1/services 匿名访问正确拦截 (HTTP 401)")

        # 1.4 管理员凭据访问管理接口应放行
        resp_admin_auth = client.get("/api/v1/services", headers={"X-API-Key": "dev-admin-key"})
        assert resp_admin_auth.status_code == 200, f"管理员访问管理接口应放行，实际: {resp_admin_auth.status_code}"
        print("  ✓ GET /api/v1/services 管理员 Key 鉴权放行通过 (HTTP 200)")

        # --- 2. 数据严格脱敏与状态暴露边界验证 ---
        print("\n[测试 2] 数据脱敏与非 active 状态服务隔离验证...")
        async def _setup_services():
            # 注册 active 业务服务
            active_svc = ServiceRegistration(
                service_id="knowledge_portal_test",
                name="企业规章制度检索库",
                endpoint_url="http://10.20.30.40:8081/mcp",
                description="检索企业制度、差旅报销与日常规范",
                owner="sec-admin-zhangsan",
                category="知识检索",
                auth_mode="platform_sso",
                auth_label="Hub 统一认证",
                auth_guide="调用能力时由 Hub 统一引导身份认证",
                auth_entry_url="https://sso.company.internal/auth",
                usage_examples=["帮我查询差旅标准", "如何申请居家办公？"],
            )
            await store.register_service(active_svc)

            # 注册内部草稿服务 (未发布 / pending / inactive)
            draft_svc = ServiceRegistration(
                service_id="internal_secret_draft",
                name="财务转账核心内部服务",
                endpoint_url="http://192.168.0.99:9090/mcp",
                description="内部高度敏感，严禁对外暴露",
                owner="cfo-private",
            )
            await store.register_service(draft_svc)
            await store.update_service_status("internal_secret_draft", ServiceStatus.INACTIVE)

            # 注册工具
            tool = RegisteredTool(
                service_id="knowledge_portal_test",
                name="query_policy",
                description="根据关键词查询公司最新制度条例",
                input_schema={
                    "type": "object",
                    "properties": {"keyword": {"type": "string", "description": "制度关键词"}},
                    "required": ["keyword"],
                },
                risk_level=ToolRiskLevel.L0,
            )
            await store.save_tools("knowledge_portal_test", [tool])

        asyncio.run(_setup_services())

        # 拉取公开能力列表进行严格断言
        caps_data = client.get("/api/v1/portal/capabilities").json()
        active_ids = [c["id"] for c in caps_data]
        assert "knowledge_portal_test" in active_ids, "active 服务必须在门户中可见"
        assert "internal_secret_draft" not in active_ids, "非 active 服务严禁泄露到门户列表"

        # 深度检查脱敏：确保没有任何卡片暴露真实 upstream endpoint_url 和 owner
        for c in caps_data:
            assert "endpoint_url" not in c, f"卡片泄露了 endpoint_url: {c}"
            assert "owner" not in c, f"卡片泄露了 owner: {c}"
            dump_str = json.dumps(c)
            assert "10.20.30.40" not in dump_str, "内网 IP 泄露"
            assert "192.168.0.99" not in dump_str, "内部 IP 泄露"
            assert "sec-admin-zhangsan" not in dump_str, "责任人隐私泄露"
        print("  ✓ 列表接口严格脱敏断言通过（无 endpoint_url，无 owner，无内网 IP）")
        print("  ✓ 停用/草稿状态服务完全隔离通过（internal_secret_draft 未暴露）")

        # 详情接口脱敏检查
        detail_resp = client.get("/api/v1/portal/capabilities/knowledge_portal_test")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["name"] == "企业规章制度检索库"
        assert "endpoint_url" not in detail
        assert "owner" not in detail
        assert detail["protocol"] == "Streamable HTTP"
        assert detail["gateway_url"].endswith("/mcp")
        assert "10.20.30.40" not in json.dumps(detail)
        print("  ✓ 详情接口脱敏断言通过（接入地址已转换为统一 Gateway 端点）")

        # 尝试访问非 active 详情：必须返回 404
        draft_resp = client.get("/api/v1/portal/capabilities/internal_secret_draft")
        assert draft_resp.status_code == 404, "非 active 详情请求必须返回 404"
        print("  ✓ 非 active 详情请求防护断言通过 (返回 404)")

        # --- 3. 真实统计数据与日志递增驱动验证 ---
        print("\n[测试 3] 真实数据驱动验证（无调用展示 0，调用后真实递增）...")
        init_total = client.get("/api/v1/portal/overview").json()["total_calls"]
        card_before = next(c for c in client.get("/api/v1/portal/capabilities").json() if c["id"] == "knowledge_portal_test")
        initial_card_calls = card_before["call_count"]

        # 模拟真实写入 1 条工具调用日志
        async def _add_call_log():
            await store.save_invocation_log({
                "service_id": "knowledge_portal_test",
                "tool_name": "knowledge_portal_test__query_policy",
                "result_status": "success",
                "duration_ms": 35.8,
                "params_summary": {"keyword": "差旅"},
            })
        asyncio.run(_add_call_log())

        # 再次查询概览与卡片
        new_total = client.get("/api/v1/portal/overview").json()["total_calls"]
        assert new_total == init_total + 1, f"总调用量必须真实递增 1 (预期 {init_total + 1}, 实际 {new_total})"
        card_after = next(c for c in client.get("/api/v1/portal/capabilities").json() if c["id"] == "knowledge_portal_test")
        assert card_after["call_count"] == initial_card_calls + 1, f"单服务调用量必须真实递增 1"
        print(f"  ✓ 调用日志写入后，全平台统计由 {init_total} 递增至 {new_total}，该服务调用量由 {initial_card_calls} 递增至 {card_after['call_count']}")

        # --- 4. 前端构建与接入配置完整性自检 ---
        print("\n[测试 4] 前端构建产物与接入面板规范自检...")
        import os
        dist_html = os.path.join("hub-admin", "dist", "index.html")
        assert os.path.exists(dist_html), "前端 dist/index.html 必须存在"
        print(f"  ✓ 前端构建产物完整存在 ({dist_html})")

        print("\n" + "=" * 70)
        print("🎉 恭喜！Capability Portal 所有核心功能、安全红线与数据真实性自检全部通过！")
        print("=" * 70)

if __name__ == "__main__":
    run_self_check()
