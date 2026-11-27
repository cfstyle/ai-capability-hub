"""AI Capability Hub - Core Entry Point

同时挂载 FastAPI 管理 API 和 FastMCP 聚合 MCP Server。
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from starlette.types import ASGIApp, Receive, Scope, Send
from urllib.parse import parse_qs

from src.api.portal import portal_router
from src.api.router import _apply_manifest_tool_overrides, api_router, discover_tools
from src.config import load_config
from src.gateway.aggregator import create_aggregator
from src.gateway.plugin_manager import plugin_manager
from src.governance.auth import TokenPayload, current_user_cv, verify_token
from src.registry.models import ServiceCredentialSchema, ServiceRegistration, ServiceStatus
from src.registry.store import RegistryStore

logger = logging.getLogger(__name__)


def _load_upstream_manifest(service_id: str) -> Optional[dict]:
    """查找并解析上游内置服务目录中的 manifest.json（优先 services/{service_id}-mcp）"""
    import json

    candidates = [
        plugin_manager.services_dir / f"{service_id}-mcp" / "manifest.json",
        plugin_manager.services_dir / service_id / "manifest.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                logger.warning("Failed to parse upstream manifest at %s: %s", path, exc)
    return None


class AuthContextMiddleware:
    """从 Authorization Header 或 ?token= 查询参数中提取 Bearer Token 并注入 current_user_cv"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    async def _send_unauthorized(send: Send, detail: str) -> None:
        import json

        body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })

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

            path = scope.get("path", "")
            user_payload = None
            token_error: Optional[str] = None
            if token:
                try:
                    user_payload = verify_token(token)
                except Exception as exc:
                    logger.debug("Token verify note: %s", exc)
                    token_error = "凭证无效或已过期"

                if user_payload is not None:
                    fastapi_app = scope.get("app")
                    store = getattr(getattr(fastapi_app, "state", None), "store", None)
                    if store is not None and await store.is_token_revoked(user_payload.sub, user_payload.iat):
                        token_error = "用户账号已停用或凭证已被吊销"
                        user_payload = None

            # 已被吊销或显式携带无效凭证访问 /mcp 时，绝不降级为 guest 逃逸 L0 限制
            if token_error and scope["type"] == "http":
                if token_error == "用户账号已停用或凭证已被吊销" or path.startswith("/mcp"):
                    await self._send_unauthorized(send, token_error)
                    return

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
    load_config.cache_clear()
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
                manifest = _load_upstream_manifest(svc.service_id)
                manifest_cred_schema: Optional[ServiceCredentialSchema] = None
                if manifest and isinstance(manifest.get("credential_schema"), dict):
                    try:
                        manifest_cred_schema = ServiceCredentialSchema(**manifest["credential_schema"])
                    except Exception as cred_exc:
                        logger.warning(
                            "Invalid credential_schema in manifest for %s: %s",
                            svc.service_id,
                            cred_exc,
                        )

                existing = await store.get_service(svc.service_id)
                if not existing:
                    reg = ServiceRegistration(
                        service_id=svc.service_id,
                        name=(manifest.get("name") if manifest else None)
                        or f"{svc.service_id.upper()} MCP Server",
                        version=str((manifest.get("version") if manifest else None) or "1.0.0"),
                        endpoint_url=svc.endpoint_url,
                        description=(manifest.get("description") if manifest else None)
                        or f"Auto-configured upstream service {svc.service_id}",
                        owner=(manifest.get("author") if manifest else None) or "",
                        credential_schema=manifest_cred_schema,
                    )
                    await store.register_service(reg)
                    discovered_saved = False
                    try:
                        tools = await discover_tools(svc.endpoint_url, svc.service_id)
                        if tools:
                            if manifest:
                                _apply_manifest_tool_overrides(tools, manifest)
                            await store.save_tools(svc.service_id, tools)
                            discovered_saved = True
                    except Exception as disc_exc:
                        logger.warning("Startup discover_tools for %s: %s", svc.service_id, disc_exc)
                    if not discovered_saved and manifest and manifest.get("tools"):
                        await store.sync_service_manifest_defaults(
                            svc.service_id,
                            credential_schema=manifest_cred_schema,
                            manifest_tools=manifest.get("tools"),
                            manifest_meta=manifest,
                        )
                elif manifest:
                    await store.sync_service_manifest_defaults(
                        svc.service_id,
                        credential_schema=manifest_cred_schema,
                        manifest_tools=manifest.get("tools"),
                        manifest_meta=manifest,
                    )

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
