import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import mcp, query_order
from fastmcp import Client

def test_query_existing():
    res = asyncio.run(query_order(order_id="ORD-2026-001"))
    assert res["success"] is True
    assert res["data"]["buyer"] == "张三"
    assert res["data"]["amount"] == 1299.00

def test_query_not_found():
    res = asyncio.run(query_order(order_id="ORD-999-NOT-FOUND"))
    assert res["success"] is False
    assert res["error_code"] == "ORDER_NOT_FOUND"

def test_mcp_client_protocol():
    async def _test():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            assert any(t.name == "query_order" for t in tools)
            call_res = await client.call_tool("query_order", {"order_id": "ORD-2026-002"})
            assert call_res.is_error is False
            assert "李四" in call_res.content[0].text
    asyncio.run(_test())
