"""AI Capability Hub - Core Entry Point

同时挂载 FastAPI 管理 API 和 FastMCP 聚合 MCP Server。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from starlette.types import ASGIApp, Receive, Scope, Send
from urllib.parse import parse_qs

from src.api.portal import portal_router
from src.api.router import api_router, discover_tools
from src.config import load_config
from src.gateway.aggregator import create_aggregator
from src.governance.auth import TokenPayload, current_user_cv, verify_token
from src.registry.models import ServiceRegistration, ServiceStatus
from src.registry.store import RegistryStore

logger = logging.getLogger(__name__)


class AuthContextMiddleware:
    """从 Authorization Header 或 ?token= 查询参数中提取 Bearer Token 并注入 current_user_cv"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            token = None
            for key, val in scope.get("headers", []):
                if key.lower() == b"authorization":
                    raw_val = val.decode("latin1").strip()
                    if raw_val.lower().startswith("bearer "):
                        token = raw_val[7:].strip()
                    elif raw_val:
                        token = raw_val
                    break

            if not token:
                query_string = scope.get("query_string", b"").decode("latin1")
                if query_string:
                    params = parse_qs(query_string)
                    if "token" in params and params["token"]:
                        token = params["token"][0]

            user_payload = None
            if token:
                try:
                    user_payload = verify_token(token)
                except Exception as exc:
                    logger.debug("Token verify note: %s", exc)

            if not user_payload:
                user_payload = TokenPayload(
                    sub="guest",
                    client_id="anonymous",
                    scopes=["hub:services:read", "hub:tools:call"],
                    exp=0,
                )

            reset_token = current_user_cv.set(user_payload)
            try:
                await self.app(scope, receive, send)
            finally:
                current_user_cv.reset(reset_token)
        else:
            await self.app(scope, receive, send)


def build_app() -> FastAPI:
    config = load_config()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))

    # 1. 初始化 DB 存储
    db_file = config.database_url.replace("sqlite:///", "")
    store = RegistryStore(db_file)

    # 2. 初始化 HubAggregator
    aggregator = create_aggregator(config.hub_name, config.hub_version, store=store)

    # 3. 获取 FastMCP ASGI app
    mcp_asgi = aggregator.get_asgi_app()

    # 4. 组合 FastAPI 与 FastMCP 的 lifespan
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Hub Core starting... database at %s", db_file)
        app.state.aggregator = aggregator
        app.state.config = config
        app.state.store = store

        # 初始化数据库表结构
        await store.init_db()

        # 加载并自动同步初始 upstream_services 到数据库与聚合代理
        for svc in config.upstream_services:
            if svc.enabled:
                existing = await store.get_service(svc.service_id)
                if not existing:
                    reg = ServiceRegistration(
                        service_id=svc.service_id,
                        name=f"{svc.service_id.upper()} MCP Server",
                        endpoint_url=svc.endpoint_url,
                        description=f"Auto-configured upstream service {svc.service_id}",
                    )
                    await store.register_service(reg)
                    try:
                        tools = await discover_tools(svc.endpoint_url, svc.service_id)
                        if tools:
                            await store.save_tools(svc.service_id, tools)
                    except Exception as disc_exc:
                        logger.warning("Startup discover_tools for %s: %s", svc.service_id, disc_exc)

                try:
                    aggregator.mount_service(svc.service_id, svc.endpoint_url)
                except Exception as exc:
                    logger.warning("Startup mount for %s: %s", svc.service_id, exc)

        # 恢复挂载数据库中已持久化且为 active 的服务（修复重启丢失挂载缺口）
        try:
            active_db_services = await store.list_services(status=ServiceStatus.ACTIVE)
            for db_svc in active_db_services:
                if db_svc.id not in aggregator._mounted_services:
                    try:
                        aggregator.mount_service(db_svc.id, db_svc.endpoint_url)
                        logger.info("Restored mount for DB service: %s -> %s", db_svc.id, db_svc.endpoint_url)
                    except Exception as exc:
                        logger.warning("Startup mount restore failed for %s: %s", db_svc.id, exc)
                        await store.update_service_status(db_svc.id, ServiceStatus.DEGRADED)
        except Exception as db_restore_exc:
            logger.warning("Failed to iterate DB services for restore: %s", db_restore_exc)

        # 启动 FastMCP 内部会话管理器
        async with mcp_asgi.lifespan(mcp_asgi):
            logger.info("Hub Core ready. MCP endpoint: %s", config.mcp_endpoint_path)
            yield

        logger.info("Hub Core shutting down...")

    fastapi_app = FastAPI(
        title=config.hub_name,
        version=config.hub_version,
        lifespan=lifespan,
    )
    fastapi_app.add_middleware(AuthContextMiddleware)

    # 5. 管理 REST API 与公开能力门户 REST API
    fastapi_app.include_router(api_router, prefix="/api/v1")
    fastapi_app.include_router(portal_router, prefix="/api/v1")

    # 6. MCP Streamable HTTP 端点挂载
    fastapi_app.mount(config.mcp_endpoint_path, mcp_asgi)

    @fastapi_app.get("/healthz")
    async def healthz():
        """存活探针"""
        return {"status": "ok"}

    @fastapi_app.get("/readyz")
    async def readyz():
        """就绪探针 (ADR-009)"""
        try:
            # 校验数据库可用性
            await store.list_services()
            return {"status": "ready"}
        except Exception as exc:
            logger.error("Ready probe failed due to database error: %s", exc)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "error": str(exc)},
            )

    return fastapi_app


app = build_app()
