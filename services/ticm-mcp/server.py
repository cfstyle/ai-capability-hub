"""TICM Mock MCP Server — 模拟债券资管 MCP 插件

1. 业务接口边界完全分离：通过 HTTP 调用独立运行的模拟 TICM 业务后端（TICM_BACKEND_URL）。
2. 工具级凭据要求：
   - ticm__trading_calendar（L0，免凭据）：匿名调用 GET /ticm/api/calendar，不携带任何个人凭据或 Cookie。
   - ticm__portfolio_summary（L1，需个人凭据）：从 Hub 注入头读取个人账号密码 -> 实际 POST /ticm/api/login 取得 Cookie -> 实际携带 Cookie 请求 GET /ticm/api/positions。
   - ticm__bond_detail（L0，免凭据）：公开债券详情查询。
3. 严禁在任何日志中输出 session 标识、Cookie 或明文密码。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import threading
import time
from datetime import date
from typing import Any, Dict, Optional

import httpx
import uvicorn
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from starlette.responses import JSONResponse

logger = logging.getLogger("ticm-mcp")
logging.basicConfig(level=logging.INFO)

host = os.getenv("TICM_HOST", "127.0.0.1")
port = int(os.getenv("TICM_PORT", "8081"))

mcp = FastMCP("TICM MCP Server")

# TICM MCP 内部维护的个人客户端 Session 缓存: f"{hub_user_id}:{credential_version}" -> ticm_session cookie
MCP_USER_SESSION_CACHE: Dict[str, str] = {}
_LOGIN_LOCKS: Dict[str, asyncio.Lock] = {}

FALLBACK_MOCK_BONDS = {
    "019547": {
        "bond_code": "019547",
        "bond_name": "21国债01",
        "issuer": "中华人民共和国财政部",
        "bond_type": "government",
        "face_value": 100.0,
        "coupon_rate": 2.85,
        "issue_date": "2021-01-22",
        "maturity_date": "2031-01-22",
        "holding_amount": 500_000_000.0,
        "market_value": 498_750_000.0,
        "currency": "CNY",
    },
    "143496": {
        "bond_code": "143496",
        "bond_name": "22万科02",
        "issuer": "万科企业股份有限公司",
        "bond_type": "corporate",
        "face_value": 100.0,
        "coupon_rate": 3.50,
        "issue_date": "2022-06-15",
        "maturity_date": "2025-06-15",
        "holding_amount": 200_000_000.0,
        "market_value": 196_400_000.0,
        "currency": "CNY",
    },
    "220210": {
        "bond_code": "220210",
        "bond_name": "22国开10",
        "issuer": "国家开发银行",
        "bond_type": "financial",
        "face_value": 100.0,
        "coupon_rate": 2.74,
        "issue_date": "2022-08-11",
        "maturity_date": "2032-08-11",
        "holding_amount": 300_000_000.0,
        "market_value": 295_800_000.0,
        "currency": "CNY",
    },
}


class TicmAuthError(Exception):
    """TICM 下游账号密码认证失败"""


class TicmDownstreamUnavailableError(Exception):
    """TICM 下游业务系统不可达"""


def _get_backend_url() -> str:
    return os.getenv("TICM_BACKEND_URL", "http://127.0.0.1:8091").rstrip("/")


def _extract_hub_credentials() -> tuple[str, str, str, str]:
    """从 Hub 注入的 HTTP 请求头提取调用者标识、凭据版本及账号密码"""
    http_req = get_http_request()
    hub_user_id = http_req.headers.get("X-Hub-User-Id")
    cred_ver = http_req.headers.get("X-Hub-Credential-Version", "1")
    creds_raw = http_req.headers.get("X-Hub-User-Credentials")

    if not hub_user_id or not creds_raw:
        raise ValueError("TICM MCP: 未接收到 Hub 注入的个人业务凭据。请确保在 Hub 门户完成了 TICM 账号密码绑定。")

    try:
        creds = json.loads(creds_raw)
    except Exception as exc:
        raise ValueError(f"TICM MCP: 业务凭据数据格式异常: {exc}")

    username = str(creds.get("username") or "").strip()
    password = str(creds.get("password") or "")
    if not username or not password:
        raise ValueError("TICM MCP: 业务凭据缺少必需的 'username' 或 'password' 字段")

    return hub_user_id, str(cred_ver), username, password


async def _login_backend(
    hub_user_id: str,
    cred_ver: str,
    username: str,
    password: str,
    force_refresh: bool = False,
) -> str:
    """通过 HTTP POST /ticm/api/login 登录模拟 TICM 业务系统，换取 ticm_session Cookie"""
    cache_key = f"{hub_user_id}:{cred_ver}"
    lock = _LOGIN_LOCKS.setdefault(cache_key, asyncio.Lock())

    async with lock:
        if not force_refresh:
            cached = MCP_USER_SESSION_CACHE.get(cache_key)
            if cached:
                return cached

        # 清理同用户旧版本号会话缓存
        user_prefix = f"{hub_user_id}:"
        for stale_key in [k for k in list(MCP_USER_SESSION_CACHE.keys()) if k.startswith(user_prefix) and k != cache_key]:
            MCP_USER_SESSION_CACHE.pop(stale_key, None)

        backend_url = _get_backend_url()
        try:
            # 每次登录使用独立 AsyncClient，绝不在用户间共享 CookieJar
            async with httpx.AsyncClient(base_url=backend_url, trust_env=False, timeout=5.0) as client:
                resp = await client.post(
                    "/ticm/api/login",
                    json={"username": username, "password": password},
                )
        except httpx.HTTPError as exc:
            raise TicmDownstreamUnavailableError(f"无法连接 TICM 登录接口: {exc}") from exc

        if resp.status_code in (401, 403):
            MCP_USER_SESSION_CACHE.pop(cache_key, None)
            logger.warning("TICM MCP: Backend rejected credentials for hub_user '%s'", hub_user_id)
            raise TicmAuthError("TICM 业务系统用户名或密码错误，请在门户更新凭据")

        if resp.status_code >= 500:
            raise TicmDownstreamUnavailableError(f"TICM 登录接口异常: HTTP {resp.status_code}")

        session_cookie = resp.cookies.get("ticm_session")
        if not session_cookie:
            raise TicmDownstreamUnavailableError("TICM 登录响应未包含 ticm_session Cookie")

        MCP_USER_SESSION_CACHE[cache_key] = session_cookie
        # 严格不在日志中打印 session_cookie 或任何 session 标识
        logger.info("TICM MCP: Authenticated user '%s' via backend login (cred_ver=%s)", hub_user_id, cred_ver)
        return session_cookie


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool(meta={"risk_level": "L0", "requires_credentials": False})
async def ticm__trading_calendar(
    year: Optional[int] = None,
    month: Optional[int] = None,
    trade_date: Optional[str] = None,
) -> dict:
    """查询银行间债券市场交易日历（公开免凭据工具，匿名执行于业务系统）。

    Args:
        year: 查询年份，默认当年
        month: 查询月份，默认当月
        trade_date: 可选的指定日期 YYYY-MM-DD，查询该日是否为交易日
    """
    params: Dict[str, Any] = {}
    if year is not None:
        params["year"] = year
    if month is not None:
        params["month"] = month
    if trade_date:
        params["trade_date"] = trade_date

    backend_url = _get_backend_url()
    try:
        async with httpx.AsyncClient(base_url=backend_url, trust_env=False, timeout=5.0) as client:
            # 匿名请求：不携带任何 X-Hub-User-* 请求头与 Cookie
            resp = await client.get("/ticm/api/calendar", params=params)
        if resp.status_code >= 500:
            return {
                "success": False,
                "error_code": "DOWNSTREAM_UNAVAILABLE",
                "message": f"TICM 交易日历接口返回错误: HTTP {resp.status_code}",
            }
        data = resp.json()
        return {"success": True, **data}
    except httpx.HTTPError as exc:
        return {
            "success": False,
            "error_code": "DOWNSTREAM_UNAVAILABLE",
            "message": f"TICM 交易日历服务不可达: {exc}",
        }


@mcp.tool(meta={"risk_level": "L1", "requires_credentials": True})
async def ticm__portfolio_summary(
    business_date: Optional[str] = None,
    bond_category: Optional[str] = None,
) -> dict:
    """获取当前登录用户的债券持仓概况（需个人 TICM 业务账号绑定，独立登录换取 Cookie）。

    Args:
        business_date: 查询日期，格式 YYYY-MM-DD，默认当天
        bond_category: 债券类别筛选 (government/corporate/financial/all)，默认 all
    """
    try:
        hub_user_id, cred_ver, username, password = _extract_hub_credentials()
    except Exception as exc:
        return {"success": False, "error_code": "UNAUTHORIZED", "message": str(exc)}

    backend_url = _get_backend_url()
    cache_key = f"{hub_user_id}:{cred_ver}"

    try:
        session_cookie = await _login_backend(hub_user_id, cred_ver, username, password, force_refresh=False)

        async with httpx.AsyncClient(
            base_url=backend_url,
            trust_env=False,
            timeout=5.0,
            cookies={"ticm_session": session_cookie},
        ) as client:
            resp = await client.get("/ticm/api/positions")

        # 若业务系统会话失效（例如改密或过期），作废本地缓存并使用当前凭据重新 POST 登录一次
        if resp.status_code == 401:
            MCP_USER_SESSION_CACHE.pop(cache_key, None)
            session_cookie = await _login_backend(hub_user_id, cred_ver, username, password, force_refresh=True)
            async with httpx.AsyncClient(
                base_url=backend_url,
                trust_env=False,
                timeout=5.0,
                cookies={"ticm_session": session_cookie},
            ) as client:
                resp = await client.get("/ticm/api/positions")

        if resp.status_code in (401, 403):
            return {
                "success": False,
                "error_code": "INVALID_CREDENTIALS",
                "message": "TICM 业务系统登录失效或密码已变更，请在门户更新个人凭据。",
            }

        if resp.status_code >= 500:
            return {
                "success": False,
                "error_code": "DOWNSTREAM_UNAVAILABLE",
                "message": f"TICM 持仓接口返回错误: HTTP {resp.status_code}",
            }

        payload = resp.json()
    except TicmAuthError as exc:
        return {
            "success": False,
            "error_code": "INVALID_CREDENTIALS",
            "message": str(exc),
        }
    except TicmDownstreamUnavailableError as exc:
        return {
            "success": False,
            "error_code": "DOWNSTREAM_UNAVAILABLE",
            "message": str(exc),
        }
    except httpx.HTTPError as exc:
        return {
            "success": False,
            "error_code": "DOWNSTREAM_UNAVAILABLE",
            "message": f"无法连接 TICM 持仓接口: {exc}",
        }

    all_positions = payload.get("positions", [])
    biz_date = business_date or date.today().isoformat()
    category = (bond_category or "all").lower()

    if category == "all":
        filtered_positions = all_positions
    else:
        filtered_positions = [p for p in all_positions if p.get("category") == category]

    total = sum(p.get("amount", 0.0) for p in filtered_positions)

    return {
        "success": True,
        "business_date": biz_date,
        "username": payload.get("username"),
        "portfolio_id": payload.get("portfolio_id"),
        "portfolio_name": payload.get("portfolio_name"),
        "owner": payload.get("real_name"),
        "total_amount": total,
        "currency": payload.get("currency", "CNY"),
        "positions": filtered_positions,
        "source": "TICM Business System",
        "isolated_session": True,
    }


@mcp.tool(meta={"risk_level": "L0", "requires_credentials": False})
async def ticm__bond_detail(bond_code: str) -> dict:
    """查询单只债券详情（公开只读，免个人凭据）。

    Args:
        bond_code: 债券代码（必填）
    """
    backend_url = os.getenv("TICM_BACKEND_URL", "").strip().rstrip("/")
    if backend_url:
        try:
            async with httpx.AsyncClient(base_url=backend_url, trust_env=False, timeout=3.0) as client:
                resp = await client.get(f"/ticm/api/bonds/{bond_code}")
            if resp.status_code == 200:
                return {**resp.json(), "data_status": "AUTHENTICATED", "source": "TICM Business System"}
            if resp.status_code == 404:
                return {
                    "bond_code": bond_code,
                    "error": "未找到该债券",
                    "available_codes": list(FALLBACK_MOCK_BONDS.keys()),
                    "data_status": "AUTHENTICATED",
                    "source": "TICM Business System",
                }
        except Exception:
            pass

    bond = FALLBACK_MOCK_BONDS.get(bond_code)
    if bond:
        return {**bond, "data_status": "MOCK", "source": "TICM Mock Server"}

    return {
        "bond_code": bond_code,
        "error": "未找到该债券",
        "available_codes": list(FALLBACK_MOCK_BONDS.keys()),
        "data_status": "MOCK",
        "source": "TICM Mock Server",
    }


# ---------------------------------------------------------------------------
# Healthcheck (Plain HTTP)
# ---------------------------------------------------------------------------


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request):
    return JSONResponse({"status": "ok", "service": "ticm-mcp"})


def _ensure_standalone_backend() -> None:
    """仅当独立直接启动 ticm-mcp 且未配置外部 TICM_BACKEND_URL 时，在独立端口拉起模拟业务后端"""
    if os.getenv("TICM_BACKEND_URL"):
        return

    from mock_ticm_backend import build_backend_app

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        backend_port = s.getsockname()[1]

    os.environ["TICM_BACKEND_URL"] = f"http://127.0.0.1:{backend_port}"
    backend_app = build_backend_app()
    config = uvicorn.Config(backend_app, host="127.0.0.1", port=backend_port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{backend_port}/healthz", timeout=0.5, trust_env=False).status_code == 200:
                break
        except Exception:
            time.sleep(0.1)


if __name__ == "__main__":
    _ensure_standalone_backend()
    mcp.run(transport="streamable-http", host=host, port=port)
