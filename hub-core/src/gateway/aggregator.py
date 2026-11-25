"""MCP 聚合代理 - 通过 FastMCP FastMCPProxy + mount 实现

Hub 对外表现为单一 MCP Server，对内作为多个下游 MCP Server 的 Client。

fastmcp >= 4.x 实际 API（已 probe 确认）：
  - FastMCPProxy(client)  位于 fastmcp.server.providers.proxy
  - FastMCP.mount(server: FastMCP, namespace=str)
  - FastMCP.http_app() 返回 StarletteWithLifespan（ASGI app）
"""

import json
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastmcp import FastMCP, Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware.middleware import Middleware, MiddlewareContext
from fastmcp.server.providers.proxy import FastMCPProxy

from src.governance.middleware import GovernanceMiddleware, current_invocation_credential_cv

logger = logging.getLogger(__name__)


class _McpErrorBridgeMiddleware(Middleware):
    """将治理中间件抛出的 PermissionError/KeyError/RuntimeError 转为 ToolError，避免 HTTP 传输层掩蔽具体原因"""

    async def on_call_tool(self, context: MiddlewareContext, call_next: Any) -> Any:
        try:
            return await call_next(context)
        except (PermissionError, KeyError, RuntimeError) as exc:
            raise ToolError(str(exc)) from exc


class HubAggregator:
    """Hub 聚合 MCP Server

    对外表现为一个 MCP Server，对内通过 FastMCPProxy + mount 代理下游服务。
    内置 GovernanceMiddleware 实现调用审计与风险治理。
    """

    def __init__(
        self,
        hub_name: str = "AI Capability Hub",
        hub_version: str = "0.2.2",
        store: Optional[Any] = None,
    ) -> None:
        self.governance_middleware = GovernanceMiddleware(store=store)
        self.mcp = FastMCP(
            hub_name,
            version=str(hub_version),
            middleware=[_McpErrorBridgeMiddleware(), self.governance_middleware],
        )
        self._mounted_services: Dict[str, str] = {}  # service_id -> endpoint_url
        self._mounted_providers: Dict[str, Any] = {}

    def set_store(self, store: Any) -> None:
        self.governance_middleware.store = store

    def mount_service(self, service_id: str, endpoint_url: str) -> None:
        """将一个远程 MCP Server 挂载为 Hub 的子服务

        Args:
            service_id: 服务标识，作为工具命名空间前缀（e.g. "ticm"）
            endpoint_url: 远程 MCP Server 的 Streamable HTTP 地址
        """
        # 下游独立 Client 连接，不透传前端客户端的 Authorization Token (ADR-004)
        # 若服务声明了个人凭据且当前调用已提取凭据上下文，按请求动态向下游注入受信任凭据头
        def _client_factory() -> Client:
            headers: Dict[str, str] = {}
            cred_ctx = current_invocation_credential_cv.get()
            if cred_ctx and cred_ctx.get("service_id") == service_id:
                env = os.getenv("HUB_ENV", "development").lower()
                if env == "production" and urlparse(endpoint_url).scheme.lower() != "https":
                    raise PermissionError(
                        f"Security policy violation: Refusing to send credentials over unprotected transport '{endpoint_url}' in production."
                    )
                headers["X-Hub-User-Id"] = str(cred_ctx["user_id"])
                headers["X-Hub-Credential-Version"] = str(cred_ctx["credential_version"])
                headers["X-Hub-User-Credentials"] = json.dumps(cred_ctx["credentials"])
            if headers:
                transport = StreamableHttpTransport(endpoint_url, headers=headers)
                return Client(transport)
            return Client(endpoint_url)

        # 若该 service_id 之前已挂载，先移除旧 provider，避免重复组件警告与路由冲突
        prev_provider = self._mounted_providers.pop(service_id, None)
        if prev_provider is not None and prev_provider in self.mcp.providers:
            self.mcp.providers.remove(prev_provider)

        proxy = FastMCPProxy(client_factory=_client_factory)
        before_count = len(self.mcp.providers)
        self.mcp.mount(proxy, namespace=service_id)
        if len(self.mcp.providers) > before_count:
            self._mounted_providers[service_id] = self.mcp.providers[-1]
        self._mounted_services[service_id] = endpoint_url
        logger.info("Mounted service: %s -> %s", service_id, endpoint_url)

    def get_asgi_app(self):
        """返回可挂载到 FastAPI 的 ASGI app"""
        return self.mcp.http_app(path="/")

    async def unmount_service(self, service_id: str) -> None:
        """动态卸载服务（P2 feature）"""
        raise NotImplementedError("Dynamic unmount is a P2 feature")



def create_aggregator(
    hub_name: str = "AI Capability Hub",
    hub_version: str = "0.2.2",
    store: Optional[Any] = None,
) -> HubAggregator:
    """工厂函数：创建 HubAggregator 实例"""
    return HubAggregator(hub_name=hub_name, hub_version=hub_version, store=store)


# 向后兼容旧名称
def create_mcp_app(
    hub_name: str = "AI Capability Hub",
    hub_version: str = "0.2.2",
) -> HubAggregator:
    return create_aggregator(hub_name=hub_name, hub_version=hub_version)

