"""模拟 TICM 债券资管核心业务系统（独立 HTTP 服务边界）

完全独立于 ticm-mcp，模拟企业内网真实的 TICM HTTP 接口：
1. POST /ticm/api/login          - 校验业务用户名/密码，签发 HttpOnly ticm_session Cookie
2. GET  /ticm/api/positions      - 校验 ticm_session Cookie，返回对应用户的个人债券持仓
3. GET  /ticm/api/calendar       - 免凭据公开交易日历接口，支持匿名访问
4. GET  /ticm/api/bonds/{code}   - 债券基础信息公开查询接口
5. POST /ticm/api/test/*         - 仅供自动化验收测试观察请求边界与模拟用户改密
"""

from __future__ import annotations

import copy
import logging
import os
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logger = logging.getLogger("ticm-backend")
logging.basicConfig(level=logging.INFO)

DEFAULT_TICM_USER_DB: Dict[str, Dict[str, Any]] = {
    "zhangsan": {
        "password": "pwd_zhangsan_123",
        "real_name": "张三 (投资经理)",
        "portfolio_id": "PF_ZHANGSAN_001",
        "portfolio_name": "张三稳健优选组合",
        "positions": [
            {
                "bond_code": "019547",
                "bond_name": "21国债01",
                "issuer": "中华人民共和国财政部",
                "category": "government",
                "amount": 1_000_000_000.0,
                "percentage": 70.0,
            },
            {
                "bond_code": "220210",
                "bond_name": "22国开10",
                "issuer": "国家开发银行",
                "category": "financial",
                "amount": 428_570_000.0,
                "percentage": 30.0,
            },
        ],
    },
    "lisi": {
        "password": "pwd_lisi_456",
        "real_name": "李四 (风控分析师)",
        "portfolio_id": "PF_LISI_002",
        "portfolio_name": "李四高收益成长组合",
        "positions": [
            {
                "bond_code": "143496",
                "bond_name": "22万科02",
                "issuer": "万科企业股份有限公司",
                "category": "corporate",
                "amount": 500_000_000.0,
                "percentage": 100.0,
            }
        ],
    },
}

MOCK_BONDS: Dict[str, Dict[str, Any]] = {
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

TICM_USER_DB: Dict[str, Dict[str, Any]] = copy.deepcopy(DEFAULT_TICM_USER_DB)
TICM_BACKEND_SESSIONS: Dict[str, Dict[str, str]] = {}
TICM_EVENT_LOG: List[Dict[str, Any]] = []

MARKET_HOLIDAYS = {
    "2026-01-01",
    "2026-05-01",
    "2026-10-01",
    "2026-10-02",
    "2026-10-05",
}


def _has_personal_credentials(request: Request) -> bool:
    """检查入站请求是否携带任何个人凭据头或会话 Cookie"""
    header_keys = {k.lower() for k in request.headers.keys()}
    sensitive_headers = {
        "x-hub-user-credentials",
        "x-hub-user-id",
        "x-hub-credential-version",
        "authorization",
    }
    if header_keys & sensitive_headers:
        return True
    if request.cookies.get("ticm_session"):
        return True
    return False


def _record_event(
    endpoint: str,
    method: str,
    status_code: int,
    request: Request,
    username: str = "",
) -> None:
    TICM_EVENT_LOG.append({
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "username": username,
        "has_session_cookie": bool(request.cookies.get("ticm_session")),
        "has_personal_credentials": _has_personal_credentials(request),
    })


async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "ticm-business-backend"})


async def ticm_login(request: Request) -> JSONResponse:
    """模拟 TICM 用户名密码登录接口，成功后签发 HttpOnly ticm_session Cookie"""
    try:
        data = await request.json()
    except Exception:
        _record_event("/ticm/api/login", "POST", 400, request)
        return JSONResponse({"error": "invalid json body"}, status_code=400)

    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")

    user_info = TICM_USER_DB.get(username)
    if not user_info or user_info["password"] != password:
        logger.warning("TICM Backend: Login failed for user '%s'", username)
        _record_event("/ticm/api/login", "POST", 401, request, username=username)
        return JSONResponse({"error": "invalid username or password"}, status_code=401)

    session_id = f"sess_{uuid.uuid4().hex}"
    TICM_BACKEND_SESSIONS[session_id] = {
        "username": username,
        "real_name": user_info["real_name"],
        "portfolio_id": user_info["portfolio_id"],
    }
    # 严禁在日志中打印 session_id 或密码
    logger.info("TICM Backend: Login successful for user '%s'", username)
    _record_event("/ticm/api/login", "POST", 200, request, username=username)

    resp = JSONResponse({"status": "ok", "message": "login successful", "username": username})
    resp.set_cookie(
        key="ticm_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


async def ticm_positions(request: Request) -> JSONResponse:
    """模拟 TICM 持仓查询，必须携带合法 ticm_session Cookie"""
    session_id = request.cookies.get("ticm_session")
    if not session_id or session_id not in TICM_BACKEND_SESSIONS:
        _record_event("/ticm/api/positions", "GET", 401, request)
        return JSONResponse({"error": "unauthorized, missing or invalid session cookie"}, status_code=401)

    session_data = TICM_BACKEND_SESSIONS[session_id]
    username = session_data["username"]
    user_info = TICM_USER_DB[username]
    _record_event("/ticm/api/positions", "GET", 200, request, username=username)

    return JSONResponse({
        "username": username,
        "real_name": user_info["real_name"],
        "portfolio_id": user_info["portfolio_id"],
        "portfolio_name": user_info["portfolio_name"],
        "positions": user_info["positions"],
        "total_amount": sum(p["amount"] for p in user_info["positions"]),
        "currency": "CNY",
    })


async def ticm_trading_calendar(request: Request) -> JSONResponse:
    """模拟 TICM 银行间债券市场交易日历（公开匿名业务接口，不需要个人会话或凭据）"""
    today = date.today()
    year = int(request.query_params.get("year") or today.year)
    month = int(request.query_params.get("month") or today.month)
    trade_date_str = request.query_params.get("trade_date")

    if trade_date_str:
        target = date.fromisoformat(trade_date_str)
        is_trading = target.weekday() < 5 and trade_date_str not in MARKET_HOLIDAYS
        _record_event("/ticm/api/calendar", "GET", 200, request)
        return JSONResponse({
            "market": "CIBM (银行间债券市场)",
            "trade_date": trade_date_str,
            "is_trading_day": is_trading,
            "settlement_cycle": "T+0 / T+1",
            "anonymous_execution": True,
            "source": "TICM Business System",
        })

    first_day = date(year, month, 1)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    trading_days: List[str] = []
    holidays: List[str] = []
    cur = first_day
    while cur < next_month:
        iso = cur.isoformat()
        if cur.weekday() < 5 and iso not in MARKET_HOLIDAYS:
            trading_days.append(iso)
        else:
            holidays.append(iso)
        cur += timedelta(days=1)

    _record_event("/ticm/api/calendar", "GET", 200, request)
    return JSONResponse({
        "market": "CIBM (银行间债券市场)",
        "year": year,
        "month": month,
        "trading_days_count": len(trading_days),
        "trading_days": trading_days[:10],
        "holidays_count": len(holidays),
        "anonymous_execution": True,
        "source": "TICM Business System",
    })


async def ticm_bond_detail(request: Request) -> JSONResponse:
    """公开债券基本信息查询"""
    bond_code = request.path_params.get("bond_code", "")
    bond = MOCK_BONDS.get(bond_code)
    if not bond:
        _record_event(f"/ticm/api/bonds/{bond_code}", "GET", 404, request)
        return JSONResponse({"error": "bond not found", "bond_code": bond_code}, status_code=404)
    _record_event(f"/ticm/api/bonds/{bond_code}", "GET", 200, request)
    return JSONResponse(bond)


async def test_events(request: Request) -> JSONResponse:
    """返回后端观察到的 HTTP 请求事件（不含密码或 session_id）"""
    return JSONResponse({"events": list(TICM_EVENT_LOG)})


async def test_reset(request: Request) -> JSONResponse:
    """重置模拟用户密码、会话与事件日志"""
    TICM_USER_DB.clear()
    TICM_USER_DB.update(copy.deepcopy(DEFAULT_TICM_USER_DB))
    TICM_BACKEND_SESSIONS.clear()
    TICM_EVENT_LOG.clear()
    return JSONResponse({"status": "reset"})


async def test_change_password(request: Request) -> JSONResponse:
    """模拟用户在 TICM 业务系统改密，并立即作废该用户在业务系统中的旧 Session"""
    data = await request.json()
    username = str(data.get("username") or "").strip()
    new_password = str(data.get("new_password") or "")
    if username not in TICM_USER_DB or not new_password:
        return JSONResponse({"error": "user not found or empty password"}, status_code=400)

    TICM_USER_DB[username]["password"] = new_password
    invalidated = [sid for sid, info in TICM_BACKEND_SESSIONS.items() if info.get("username") == username]
    for sid in invalidated:
        TICM_BACKEND_SESSIONS.pop(sid, None)

    logger.info("TICM Backend: Password changed for user '%s', invalidated %d active sessions", username, len(invalidated))
    return JSONResponse({"status": "ok", "username": username, "invalidated_sessions": len(invalidated)})


def build_backend_app() -> Starlette:
    routes = [
        Route("/healthz", healthz, methods=["GET"]),
        Route("/ticm/api/login", ticm_login, methods=["POST"]),
        Route("/ticm/api/positions", ticm_positions, methods=["GET"]),
        Route("/ticm/api/calendar", ticm_trading_calendar, methods=["GET"]),
        Route("/ticm/api/bonds/{bond_code}", ticm_bond_detail, methods=["GET"]),
        Route("/ticm/api/test/events", test_events, methods=["GET"]),
        Route("/ticm/api/test/reset", test_reset, methods=["POST"]),
        Route("/ticm/api/test/change-password", test_change_password, methods=["POST"]),
    ]
    return Starlette(routes=routes)


app = build_backend_app()

if __name__ == "__main__":
    host = os.getenv("TICM_BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("TICM_BACKEND_PORT", "8091"))
    uvicorn.run(app, host=host, port=port)
