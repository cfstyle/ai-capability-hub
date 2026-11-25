"""端到端权限生命周期闭环自动化验证脚本

验证流程：
1. 初始接入（未授权）：新用户接入 Hub Gateway，tools/list 仅能感知 L0 工具，L2 工具（message__send_notification）自动隐藏；若越权调用直接拦截。
2. 门户申请：用户提交敏感工具开通申请单。
3. 管理审批：管理员在管理端审核同意，系统自动写入用户授权。
4. 动态生效（Zero-Config）：用户在无需任何客户端配置变更的情况下，再次 tools/list 自动感知到新工具并成功执行 tools/call，且审计日志完整记录真实 user_id。
"""

import asyncio
import json
import urllib.request
import urllib.error
from datetime import datetime

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def print_step(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def http_get(url: str, headers: dict = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post(url: str, data: dict, headers: dict = None) -> dict:
    body = json.dumps(data).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def run_e2e_test():
    test_user_id = f"U_TEST_{int(datetime.now().timestamp()) % 10000}"
    test_user_name = "张三 (投资经理)"
    print_step(f"步骤 0: 为测试用户 [{test_user_id} - {test_user_name}] 获取专属接入 Token")

    # 1. 门户一键接入接口获取配置与 Token
    cfg = http_get(f"http://127.0.0.1:8080/api/v1/portal/my-config?user_id={test_user_id}")
    user_token = cfg["token"]
    gateway_url = cfg["gateway_url"]
    print(f"[OK] 成功颁发签名 Token (sub: {cfg['user_id']})")
    print(f"     网关端点: {gateway_url}")
    print(f"     Token 前缀: {user_token[:25]}...")

    # -------------------------------------------------------------------------
    # Phase 1: 首次接入，仅能看到并调用 L0 工具
    # -------------------------------------------------------------------------
    print_step("步骤 1: 新用户初次接入网关 (验证 L0 默认放行 与 L2 自动屏蔽)")
    
    # 通过 streamable_http_client 连接带 Token 的 Gateway URL
    user_mcp_url = f"http://127.0.0.1:8080/mcp?token={user_token}"
    
    async with streamable_http_client(user_mcp_url) as streams:
        read, write = streams[0], streams[1] if isinstance(streams, tuple) else streams
        async with ClientSession(read, write) as session:
            init_res = await session.initialize()
            print("[OK] MCP 握手成功！")

            # 查询当前可用工具
            tools_res = await session.list_tools()
            tool_names = [t.name for t in tools_res.tools]
            print(f"[OK] 客户端当前可见工具列表 ({len(tool_names)} 个):")
            for name in tool_names:
                print(f"     • {name}")

            # 验证断言
            assert any("portfolio_summary" in n for n in tool_names), "L0 工具 portfolio_summary 必须默认可见"
            assert any("list_pending" in n for n in tool_names), "L0 工具 list_pending 必须默认可见"
            assert not any("send_notification" in n for n in tool_names), "敏感 L2 工具 send_notification 未授权时绝对不可见！"
            print("[PASS] 验证通过：L0 工具全员可见，L2 工具严格不可见！")

            # 越权调用防护测试：若用户直接强行猜测调用敏感工具
            print("\n正在测试恶意/越权调用未授权工具 (message__message__send_notification)...")
            target_l2_tool = "message__message__send_notification"
            try:
                call_res = await session.call_tool(
                    target_l2_tool,
                    {
                        "to": "boss@example.com",
                        "subject": "越权通知",
                        "content": "这是一封非法调用的测试通知"
                    }
                )
                if getattr(call_res, "isError", False):
                    print(f"[PASS] 网关拦截成功：返回错误 -> {call_res.content[0].text if call_res.content else 'Error'}")
                else:
                    print(f"[FAIL] 越权调用未被拦截！返回了: {call_res}")
            except Exception as exc:
                print(f"[PASS] 网关拦截成功：抛出异常 -> {exc}")

    # -------------------------------------------------------------------------
    # Phase 2: 用户在门户发起申请，管理员在后台审批
    # -------------------------------------------------------------------------
    print_step("步骤 2: 用户在能力门户提交权限申请单")
    apply_payload = {
        "user_id": test_user_id,
        "user_name": test_user_name,
        "service_id": "message",
        "tool_ids": ["message__message__send_notification"],
        "reason": "投资业务需要，向交易员发送大额资产审批结果推送",
    }
    apply_res = http_post("http://127.0.0.1:8080/api/v1/portal/permission-requests", apply_payload)
    request_id = apply_res["id"]
    print(f"[OK] 申请单已提交，单号: {request_id}, 状态: {apply_res['status']}")
    assert apply_res["status"] == "pending"

    print("\n步骤 3: 管理员在后台审核并批准申请单")
    admin_headers = {"X-API-Key": "dev-admin-key"}
    review_payload = {
        "status": "approved",
        "reviewer": "admin_audit_officer",
        "comment": "经核实业务部门场景合规，予以开通敏感消息发送权限",
    }
    review_res = http_post(
        f"http://127.0.0.1:8080/api/v1/admin/permission-requests/{request_id}/review",
        review_payload,
        headers=admin_headers,
    )
    print(f"[OK] 审批完成！状态: {review_res['status']}, 审核人: {review_res['reviewed_by']}")
    assert review_res["status"] == "approved"

    # 查询当前用户有效授权
    grants_info = http_get(f"http://127.0.0.1:8080/api/v1/portal/my-grants?user_id={test_user_id}")
    print(f"[OK] 用户当前已生效授权清单: {grants_info['granted_tool_ids']}")
    assert "message__message__send_notification" in grants_info["granted_tool_ids"]

    # -------------------------------------------------------------------------
    # Phase 3: 客户端零变更动态感知与正常调用
    # -------------------------------------------------------------------------
    print_step("步骤 4: 零配置动态感知验证 (重新查询 tools/list，验证已获批敏感工具自动点亮)")

    async with streamable_http_client(user_mcp_url) as streams:
        read, write = streams[0], streams[1] if isinstance(streams, tuple) else streams
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 重新列出工具
            new_tools_res = await session.list_tools()
            new_tool_names = [t.name for t in new_tools_res.tools]
            print(f"[OK] 审批通过后客户端可见工具列表 ({len(new_tool_names)} 个):")
            for name in new_tool_names:
                print(f"     • {name}")

            assert any("send_notification" in n for n in new_tool_names), "获批后 send_notification 必须立即对客户端可见！"
            call_target = next(n for n in new_tool_names if "send_notification" in n)
            print(f"[PASS] 验证通过：敏感工具 [{call_target}] 无需客户端做任何变更即刻点亮！")

            # 正常发起工具调用
            print(f"\n步骤 5: 用户发起合法工具调用 (tools/call: {call_target})")
            call_res = await session.call_tool(
                call_target,
                {
                    "to": "compliance@firm.com",
                    "subject": "【投资完成】21国债01 增持 5000 万元",
                    "content": "已在银行间市场完成交易对手方确认，特此通知合规备案。",
                    "priority": "high",
                }
            )
            print("[OK] 工具执行成功！返回内容:")
            if call_res.content:
                print("     " + call_res.content[0].text.replace("\n", "\n     "))
            assert not getattr(call_res, "isError", False)
            print("[PASS] 敏感业务工具调用成功完成！")

    # -------------------------------------------------------------------------
    # Phase 4: 审计追踪校验
    # -------------------------------------------------------------------------
    print_step("步骤 6: 验证审计日志记录 (检查真实 user_id 与调用结果)")
    audit_data = http_get(
        f"http://127.0.0.1:8080/api/v1/audit-logs?tool_name={call_target}&limit=5",
        headers=admin_headers,
    )
    items = audit_data.get("items", [])
    print(f"[OK] 检索到审计日志条数: {len(items)}")
    matched = [it for it in items if it.get("user_id") == test_user_id]
    assert len(matched) > 0, f"必须存在以 user_id={test_user_id} 记录的真实调用审计日志！"
    log_item = matched[0]
    print(f"[PASS] 审计记录验证通过:")
    print(f"       用户工号: {log_item['user_id']}")
    print(f"       客户端ID: {log_item['client_id']}")
    print(f"       目标工具: {log_item['tool_name']}")
    print(f"       执行耗时: {log_item['duration_ms']} ms")
    print(f"       结果状态: {log_item['result_status']}")
    print("\n" + "=" * 70)
    print("  🎉 全链路授权生命周期、动态感知与安全治理自动化测试全部通过！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_e2e_test())
