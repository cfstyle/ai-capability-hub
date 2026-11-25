from __future__ import annotations
import logging, os
from typing import Any, Dict
from fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP("Order Service")

ORDERS_DB = {
    "ORD-2026-001": {
        "order_id": "ORD-2026-001",
        "buyer": "张三",
        "amount": 1299.00,
        "status": "PAID",
        "items": ["智能降噪耳机"],
        "created_at": "2026-11-24 10:00:00",
    },
    "ORD-2026-002": {
        "order_id": "ORD-2026-002",
        "buyer": "李四",
        "amount": 88.50,
        "status": "SHIPPED",
        "items": ["Type-C 数据线 2米"],
        "created_at": "2026-11-24 11:30:00",
    },
}

@mcp.tool()
async def query_order(order_id: str) -> Dict[str, Any]:
    """根据订单号查询订单状态与购买明细。"""
    clean_id = (order_id or "").strip()
    if not clean_id:
        return {"success": False, "error_code": "INVALID_PARAMS", "message": "订单号不能为空"}

    order = ORDERS_DB.get(clean_id)
    if not order:
        return {
            "success": False,
            "error_code": "ORDER_NOT_FOUND",
            "message": f"未找到订单 '{clean_id}'",
            "available_order_examples": list(ORDERS_DB.keys()),
        }

    return {"success": True, "data": order}

@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "Order Service", "tools_count": 1})

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="streamable-http", host=host, port=port)
