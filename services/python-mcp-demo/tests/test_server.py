"""测试 python-mcp-demo 的工具逻辑与 MCP 协议端到端契约"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import mcp, get_demo_data, process_demo_task
from fastmcp import Client


def test_get_demo_data_list():
    """验证列表查询逻辑"""
    res = asyncio.run(get_demo_data())
    assert res["success"] is True
    assert res["total"] >= 3


def test_get_demo_data_single():
    """验证单条精确查询"""
    res = asyncio.run(get_demo_data(item_id="item_001"))
    assert res["success"] is True
    assert res["data"]["id"] == "item_001"


def test_get_demo_data_not_found():
    """验证非法/不存在 ID 的结构化错误返回（不抛出崩溃）"""
    res = asyncio.run(get_demo_data(item_id="item_999_non_exist"))
    assert res["success"] is False
    assert res["error_code"] == "NOT_FOUND"


def test_process_demo_task_update_status():
    """验证业务写操作"""
    res = asyncio.run(process_demo_task(
        action_type="update_status",
        target_id="item_001",
        payload={"new_status": "in_progress"},
    ))
    assert res["success"] is True
    assert res["updated_record"]["status"] == "in_progress"


def test_mcp_client_discovery_and_call():
    """验证 FastMCP Client 协议层工具发现与调用 (在内存中免端口极速运行)"""
    async def _run_client_test():
        async with Client(mcp) as client:
            # 1. 工具发现
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            assert "get_demo_data" in tool_names
            assert "process_demo_task" in tool_names

            # 2. 工具调用
            call_res = await client.call_tool("get_demo_data", {"item_id": "item_001"})
            assert call_res.is_error is False
            assert "演示指标 A" in call_res.content[0].text

    asyncio.run(_run_client_test())
