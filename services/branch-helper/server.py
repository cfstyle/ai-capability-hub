"""网点运营助手 MCP 测试插件 (遵循 AI Capability Hub 标准规范)

包含两个演示工具：
1. query_exchange_rate (L0, 免凭据): 模拟外汇牌价查询，上传发布后即可直接在线调试。
2. query_my_branch_quota (L1, 需个人参数透传): 读取 Hub 注入的 X-Hub-User-Credentials，
   用于验证「前台参数绑定 -> 后台允许个人参数透传 -> 网关安全注入」完整闭环。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Literal

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from starlette.responses import JSONResponse

HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_PORT", "8089"))
SERVICE_NAME = os.getenv("MCP_SERVICE_NAME", "branch-helper-mcp")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("branch_helper_mcp")

mcp = FastMCP(SERVICE_NAME)

MOCK_RATES: Dict[str, Dict[str, Any]] = {
    "USD": {"currency": "USD", "name": "美元", "buy": 7.1820, "sell": 7.2110, "unit": 1},
    "EUR": {"currency": "EUR", "name": "欧元", "buy": 7.7950, "sell": 7.8320, "unit": 1},
    "HKD": {"currency": "HKD", "name": "港币", "buy": 0.9210, "sell": 0.9265, "unit": 1},
    "JPY": {"currency": "JPY", "name": "日元(百)", "buy": 4.7120, "sell": 4.7490, "unit": 100},
}


@mcp.tool()
async def query_exchange_rate(
    currency: Literal["USD", "EUR", "HKD", "JPY"] = "USD",
) -> Dict[str, Any]:
    """查询常用币种模拟参考牌价（L0 公开免凭据）。

    Args:
        currency: 币种代码，可选 USD、EUR、HKD、JPY，默认 USD。
    """
    code = currency.upper().strip()
    rate = MOCK_RATES.get(code)
    if not rate:
        return {
            "success": False,
            "error_code": "UNSUPPORTED_CURRENCY",
            "message": f"暂不支持币种 '{code}'，可选: {', '.join(MOCK_RATES.keys())}",
        }
    return {
        "success": True,
        "data": {
            **rate,
            "quote_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "branch-helper-mock",
        },
    }


@mcp.tool()
async def query_my_branch_quota(
    biz_type: Literal["loan", "deposit", "fx"] = "loan",
) -> Dict[str, Any]:
    """查询个人绑定网点的当日业务额度（L1 需个人参数透传）。

    Args:
        biz_type: 业务条线，可选 loan（信贷）、deposit（存款）、fx（外汇）。
    """
    http_req = get_http_request()
    hub_user_id = http_req.headers.get("X-Hub-User-Id", "")
    cred_version = http_req.headers.get("X-Hub-Credential-Version", "1")
    creds_raw = http_req.headers.get("X-Hub-User-Credentials", "")

    if not hub_user_id or not creds_raw:
        return {
            "success": False,
            "error_code": "INVALID_CREDENTIALS",
            "message": "未收到 Hub 透传的个人参数，请确认已在前台绑定网点参数且管理员已开启「允许个人参数透传」。",
        }

    try:
        creds = json.loads(creds_raw)
    except Exception as exc:
        return {
            "success": False,
            "error_code": "INVALID_CREDENTIALS",
            "message": f"透传参数解析异常: {exc}",
        }

    branch_code = str(creds.get("branch_code") or "").strip()
    operator_token = str(creds.get("operator_token") or "").strip()
    if not branch_code or not operator_token:
        return {
            "success": False,
            "error_code": "INVALID_CREDENTIALS",
            "message": "缺少必填参数 branch_code 或 operator_token。",
        }

    masked_token = operator_token[:2] + "***" if len(operator_token) > 2 else "***"
    quota_map = {
        "loan": {"label": "普惠信贷额度", "total_wan": 5000, "used_wan": 1820, "remain_wan": 3180},
        "deposit": {"label": "特色存款额度", "total_wan": 8000, "used_wan": 4300, "remain_wan": 3700},
        "fx": {"label": "结售汇平盘额度", "total_wan": 2000, "used_wan": 650, "remain_wan": 1350},
    }
    quota = quota_map.get(biz_type, quota_map["loan"])
    return {
        "success": True,
        "data": {
            "emp_no": hub_user_id,
            "branch_code": branch_code,
            "operator_token_masked": masked_token,
            "credential_version": cred_version,
            "biz_type": biz_type,
            **quota,
            "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }


@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(request):
    """标准健康检查接口"""
    return JSONResponse({
        "status": "healthy",
        "service": SERVICE_NAME,
        "tools_count": 2,
    })


if __name__ == "__main__":
    logger.info("Starting %s on %s:%d (Streamable HTTP)", SERVICE_NAME, HOST, PORT)
    mcp.run(transport="streamable-http", host=HOST, port=PORT)
