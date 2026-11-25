"""Python MCP 标准示例服务 (Standard FastMCP Plugin Demo)

AI Capability Hub 官方推荐的 MCP 插件标准实现范例：
1. 全面采用异步函数 (async def)，保障高并发不阻塞事件循环。
2. 规范的 Docstring 与类型注解，让 LLM 能够精准理解参数意图。
3. 健壮的业务异常捕获，返回结构化错误而非抛出崩溃。
4. 包含标准的 /healthz 健康检查端点。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP
from starlette.responses import JSONResponse

# 1. 基础配置
HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "8000"))
SERVICE_NAME = os.getenv("MCP_SERVICE_NAME", "Python MCP Demo")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mcp_server")

# 2. 初始化 FastMCP 服务
mcp = FastMCP(SERVICE_NAME)

# ---------------------------------------------------------------------------
# 业务 Mock 数据 / 客户端初始化区域
# ---------------------------------------------------------------------------
DEMO_DATABASE: Dict[str, Dict[str, Any]] = {
    "item_001": {"id": "item_001", "name": "演示指标 A", "status": "active", "value": 98.5},
    "item_002": {"id": "item_002", "name": "演示指标 B", "status": "pending", "value": 42.0},
    "item_003": {"id": "item_003", "name": "演示指标 C", "status": "disabled", "value": 0.0},
}


# ---------------------------------------------------------------------------
# Tools 业务工具定义
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_demo_data(
    item_id: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """查询演示数据列表或单条明细。

    Args:
        item_id: 可选的条目唯一ID（如 "item_001"）。若指定则返回单条详情。
        status_filter: 可选的状态过滤条件 ("active", "pending", "disabled")。

    Returns:
        包含查询结果、总条数及执行状态的字典。
    """
    logger.info("Executing get_demo_data: item_id=%s, filter=%s", item_id, status_filter)
    try:
        # 单条精确查询
        if item_id:
            record = DEMO_DATABASE.get(item_id)
            if not record:
                return {
                    "success": False,
                    "error_code": "NOT_FOUND",
                    "message": f"未找到 ID 为 '{item_id}' 的数据记录",
                    "available_ids": list(DEMO_DATABASE.keys()),
                }
            return {"success": True, "data": record}

        # 列表过滤查询
        results: List[Dict[str, Any]] = list(DEMO_DATABASE.values())
        if status_filter:
            results = [r for r in results if r["status"] == status_filter.lower()]

        return {
            "success": True,
            "total": len(results),
            "data": results,
            "source": "demo_database"
        }
    except Exception as exc:
        logger.exception("Error querying demo data: %s", exc)
        return {"success": False, "error_code": "SYSTEM_ERROR", "message": str(exc)}


@mcp.tool()
async def process_demo_task(
    action_type: str,
    target_id: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """执行业务写操作或运维动作。

    Args:
        action_type: 动作类型，可选："update_status"（更新状态）、"calculate"（重新核算）。
        target_id: 操作目标对象的 ID（如 "item_001"）。
        payload: 额外业务参数字典，如 {"new_status": "active"}。

    Returns:
        包含操作执行结果及变动后数据的字典。
    """
    logger.info("Executing process_demo_task: action=%s, target=%s", action_type, target_id)
    payload = payload or {}

    try:
        # 目标校验
        if target_id not in DEMO_DATABASE:
            return {
                "success": False,
                "error_code": "TARGET_NOT_FOUND",
                "message": f"操作失败：目标 '{target_id}' 不存在",
            }

        # 动作分支
        if action_type == "update_status":
            new_status = payload.get("new_status")
            if not new_status:
                return {
                    "success": False,
                    "error_code": "INVALID_PARAMS",
                    "message": "参数缺失：update_status 动作必须在 payload 中提供 'new_status'",
                }
            DEMO_DATABASE[target_id]["status"] = str(new_status)
            return {
                "success": True,
                "message": f"目标 {target_id} 状态已更新为 {new_status}",
                "updated_record": DEMO_DATABASE[target_id],
            }

        elif action_type == "calculate":
            multiplier = float(payload.get("multiplier", 1.5))
            old_val = DEMO_DATABASE[target_id]["value"]
            DEMO_DATABASE[target_id]["value"] = round(old_val * multiplier, 2)
            return {
                "success": True,
                "message": f"核算完成，倍率={multiplier}",
                "old_value": old_val,
                "new_value": DEMO_DATABASE[target_id]["value"],
            }

        else:
            return {
                "success": False,
                "error_code": "UNSUPPORTED_ACTION",
                "message": f"不支持的动作类型: '{action_type}'。支持的类型：update_status, calculate",
            }

    except Exception as exc:
        logger.exception("Error executing task: %s", exc)
        return {"success": False, "error_code": "EXECUTION_FAILED", "message": str(exc)}


# ---------------------------------------------------------------------------
# 健康检查路由 (HTTP /healthz)
# ---------------------------------------------------------------------------

@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(request):
    """供容器与网关做存活及就绪性探测"""
    return JSONResponse({
        "status": "healthy",
        "service": SERVICE_NAME,
        "tools_count": 2
    })


# ---------------------------------------------------------------------------
# 服务主入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting %s on %s:%d (Streamable HTTP)", SERVICE_NAME, HOST, PORT)
    mcp.run(transport="streamable-http", host=HOST, port=PORT)
