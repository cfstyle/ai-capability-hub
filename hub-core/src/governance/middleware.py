"""治理中间件

实现：
1. 风险分级与权限检查（on_call_tool, on_list_tools）
2. 结构化审计日志记录（调用时间、用户、工具、耗时、结果）
3. 参数脱敏
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from fastmcp.server.middleware.middleware import Middleware, MiddlewareContext
from fastmcp.tools.base import Tool
from mcp import types as mt

from src.governance.audit import AuditLogger
from src.governance.auth import TokenPayload, get_current_user
from src.registry.models import ServiceStatus, ToolRiskLevel
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.registry.store import RegistryStore

logger = logging.getLogger(__name__)

# 当前工具调用的凭据上下文 (仅供 Hub Gateway 代理层向受信任的下游服务传递)
current_invocation_credential_cv: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "current_invocation_credential_cv", default=None
)

# 敏感字段关键字（用于参数脱敏）
SENSITIVE_KEYS = {"password", "secret", "token", "authorization", "api_key", "apikey", "credential"}


def desensitize_params(params: Any) -> Any:
    """递归对入参字典、列表或标量进行敏感信息脱敏"""
    if not params:
        return {} if isinstance(params, dict) else params
    if isinstance(params, dict):
        clean: Dict[str, Any] = {}
        for k, v in params.items():
            if any(sk in str(k).lower() for sk in SENSITIVE_KEYS):
                clean[k] = "***"
            else:
                clean[k] = desensitize_params(v)
        return clean
    elif isinstance(params, (list, tuple)):
        return [desensitize_params(item) for item in params]
    return params


async def resolve_tool_and_service(
    store: RegistryStore,
    tool_name: str,
) -> Tuple[Optional[Any], Optional[Any]]:
    """精确解析工具和对应服务，严禁子串与模糊匹配"""
    # 1. 优先按 namespace_name 或 id 查库
    tool_meta = await store.get_tool_by_namespace_name(tool_name)
    if not tool_meta:
        # 2. 精确比对已注册工具的 id / namespace_name
        all_tools = await store.list_tools()
        for t in all_tools:
            if (
                t.id == tool_name
                or t.namespace_name == tool_name
                or f"{t.service_id}__{t.name}" == tool_name
                or f"{t.service_id}_{t.name}" == tool_name
            ):
                tool_meta = t
                break
        if not tool_meta:
            # 仅当名称在全量中唯一存在时允许匹配
            exact_name_matches = [t for t in all_tools if t.name == tool_name]
            if len(exact_name_matches) == 1:
                tool_meta = exact_name_matches[0]

    svc = None
    if tool_meta:
        svc = await store.get_service(tool_meta.service_id)
    return tool_meta, svc


class GovernanceMiddleware(Middleware):
    """Hub 核心治理中间件

    拦截 MCP 请求生命周期，执行安全审计与风险控制。
    """

    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        store: Optional[RegistryStore] = None,
    ) -> None:
        self.audit_logger = audit_logger or AuditLogger()
        self.store = store

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: Any,
    ) -> Sequence[Tool]:
        """拦截 tools/list：按用户权限与服务状态动态过滤工具清单 (Zero-Config 权限动态感知)"""
        tools = await call_next(context)
        user = get_current_user()

        # 如果没有配置 store，保持原样
        if not self.store:
            return tools

        is_admin = bool(user and "hub:admin" in user.scopes)

        # 检查服务可用状态
        services = await self.store.list_services()
        active_service_ids = {s.id for s in services if s.status == ServiceStatus.ACTIVE}

        # 查询所有已注册工具，构建精确映射
        all_registered_tools = await self.store.list_tools()
        tool_lookup: Dict[str, Any] = {}
        for t in all_registered_tools:
            tool_lookup[t.id] = t
            tool_lookup[t.namespace_name] = t
            tool_lookup[f"{t.service_id}__{t.name}"] = t
            tool_lookup[f"{t.service_id}_{t.name}"] = t

        user_id = user.sub if user else "guest"
        granted_tool_ids = set(await self.store.get_user_granted_tool_ids(user_id))
        disabled_service_ids = await self.store.get_user_disabled_service_ids(user_id)

        filtered_tools = []
        for tool_item in tools:
            t_name = getattr(tool_item, "name", "")
            tool_meta = tool_lookup.get(t_name)
            if not tool_meta:
                matches = [t for t in all_registered_tools if t.name == t_name]
                if len(matches) == 1:
                    tool_meta = matches[0]

            if tool_meta:
                # 检查所属服务是否正常启用，以及当前用户个人装配开关是否关闭
                if tool_meta.service_id not in active_service_ids:
                    continue
                if tool_meta.service_id in disabled_service_ids:
                    continue

                if is_admin:
                    filtered_tools.append(tool_item)
                elif tool_meta.risk_level == ToolRiskLevel.L0:
                    filtered_tools.append(tool_item)
                elif tool_meta.id in granted_tool_ids or tool_meta.namespace_name in granted_tool_ids:
                    filtered_tools.append(tool_item)
            else:
                if is_admin:
                    filtered_tools.append(tool_item)

        return filtered_tools

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: Any,
    ) -> Any:
        """拦截 tools/call：检查服务可用状态、权限校验、记录耗时、入参脱敏与结构化审计日志"""
        message = context.message
        tool_name = getattr(message, "name", "unknown")
        raw_arguments = getattr(message, "arguments", {}) or {}
        clean_params = desensitize_params(raw_arguments)

        # 1. 提取当前上下文用户
        user = get_current_user()
        user_id = user.sub if user else "guest"
        client_id = user.client_id if user and user.client_id else "mcp-client"

        start_time = time.time()
        service_id = tool_name.split("__")[0] if "__" in tool_name else (tool_name.split("_")[0] if "_" in tool_name else "hub")
        tool_id_for_log = tool_name
        audit_recorded = False
        credential_context: Optional[Dict[str, Any]] = None

        async def _record_audit(status_str: str, dur_ms: float):
            nonlocal audit_recorded
            audit_recorded = True
            self.audit_logger.log_tool_call(
                user_id=user_id,
                client_id=client_id,
                tool_name=tool_id_for_log,
                service_id=service_id,
                params_summary=clean_params,
                result_status=status_str,
                duration_ms=dur_ms,
            )
            if self.store:
                try:
                    await self.store.save_invocation_log({
                        "user_id": user_id,
                        "client_id": client_id,
                        "tool_name": tool_id_for_log,
                        "service_id": service_id,
                        "params_summary": clean_params,
                        "result_status": status_str,
                        "duration_ms": dur_ms,
                    })
                except Exception as log_exc:
                    logger.warning("Failed to persist invocation log: %s", log_exc)

        # 统一判定顺序：先所属服务状态 -> 工具是否已登记 -> 主体授权
        if self.store:
            # 1. 优先检查所属服务是否已被禁用
            candidate_service_id = tool_name.split("__")[0] if "__" in tool_name else (tool_name.split("_")[0] if "_" in tool_name else "hub")
            svc_by_prefix = await self.store.get_service(candidate_service_id)
            if svc_by_prefix and svc_by_prefix.status != ServiceStatus.ACTIVE:
                service_id = svc_by_prefix.id
                dur = round((time.time() - start_time) * 1000, 2)
                err_text = f"rejected: service '{service_id}' is {svc_by_prefix.status.value}"
                logger.warning(
                    "Blocked call to inactive service '%s' (status: %s, tool: %s, user: %s)",
                    service_id,
                    svc_by_prefix.status.value,
                    tool_name,
                    user_id,
                )
                await _record_audit(err_text, dur)
                raise RuntimeError(
                    f"Service '{service_id}' is currently {svc_by_prefix.status.value}. Call to '{tool_name}' is blocked by Gateway."
                )

            tool_meta, svc = await resolve_tool_and_service(self.store, tool_name)
            if tool_meta:
                service_id = tool_meta.service_id
                tool_id_for_log = tool_meta.id

            # 2. 工具未登记判定
            if not tool_meta:
                dur = round((time.time() - start_time) * 1000, 2)
                err_text = f"rejected: unknown tool '{tool_name}'"
                logger.warning("Blocked unknown tool call '%s' by user '%s'", tool_name, user_id)
                await _record_audit(err_text, dur)
                raise KeyError(f"Tool '{tool_name}' not found in registry")

            # 3. 关联服务状态判定
            if not svc or svc.status != ServiceStatus.ACTIVE:
                status_val = svc.status.value if svc else "unknown"
                dur = round((time.time() - start_time) * 1000, 2)
                err_text = f"rejected: service '{service_id}' is {status_val}"
                logger.warning(
                    "Blocked call to inactive service '%s' (status: %s, tool: %s, user: %s)",
                    service_id,
                    status_val,
                    tool_name,
                    user_id,
                )
                await _record_audit(err_text, dur)
                raise RuntimeError(
                    f"Service '{service_id}' is currently {status_val}. Call to '{tool_name}' is blocked by Gateway."
                )

            # 3.5 个人装配开关判定（默认开启，仅显式关闭时拦截）
            disabled_service_ids = await self.store.get_user_disabled_service_ids(user_id)
            if service_id in disabled_service_ids:
                dur = round((time.time() - start_time) * 1000, 2)
                err_text = f"rejected: service '{service_id}' disabled in personal settings"
                logger.warning(
                    "Blocked call to personally disabled service '%s' (tool: %s, user: %s)",
                    service_id,
                    tool_name,
                    user_id,
                )
                await _record_audit(err_text, dur)
                raise PermissionError(
                    f"Service '{service_id}' is disabled in your personal settings"
                )

            # 3. 授权判定 (Admin 全通；L0 风险全员可用；非 L0 需精确匹配已获授权，杜绝模糊放行)
            is_admin = bool(user and "hub:admin" in user.scopes)
            if not is_admin and tool_meta.risk_level != ToolRiskLevel.L0:
                granted_ids = set(await self.store.get_user_granted_tool_ids(user_id))
                is_granted = (tool_meta.id in granted_ids) or (tool_meta.namespace_name in granted_ids)
                if not is_granted:
                    dur = round((time.time() - start_time) * 1000, 2)
                    err_text = f"rejected: permission denied for tool '{tool_meta.id}' ({tool_meta.risk_level.value})"
                    logger.warning(
                        "Blocked unauthorized tool call: user '%s' attempted to call '%s' (risk: %s)",
                        user_id,
                        tool_name,
                        tool_meta.risk_level.value,
                    )
                    await _record_audit(err_text, dur)
                    raise PermissionError(
                        f"Permission denied: Tool '{tool_name}' ({tool_meta.risk_level.value}) requires explicit authorization. Please apply in Capability Portal."
                    )

            # 4. 业务凭据判定与隔离上下文提取（按具体工具声明判定）
            tool_requires_creds = bool(getattr(tool_meta, "requires_credentials", False))
            if tool_requires_creds:
                if not svc.credential_schema or not svc.credential_schema.enabled:
                    dur = round((time.time() - start_time) * 1000, 2)
                    err_text = f"rejected: tool '{tool_meta.id}' requires credentials but service '{service_id}' has no credential_schema enabled"
                    logger.error("Blocked credentialed tool '%s' on service '%s' without credential_schema", tool_meta.id, service_id)
                    await _record_audit(err_text, dur)
                    raise PermissionError(
                        f"Service '{service_id}' has not declared credential_schema for credentialed tool '{tool_name}'."
                    )

                is_trusted = (
                    bool(getattr(svc, "trusted_credential_recipient", False))
                    and getattr(svc, "trusted_credential_version", None) == svc.version
                    and getattr(svc, "trusted_credential_endpoint_url", None) == svc.endpoint_url
                )
                if not is_trusted:
                    dur = round((time.time() - start_time) * 1000, 2)
                    err_text = f"rejected: service '{service_id}' is not a trusted credential recipient (or version/endpoint changed)"
                    logger.error("Blocked credential dispatch to untrusted or changed service '%s'", service_id)
                    await _record_audit(err_text, dur)
                    raise PermissionError(
                        f"Security policy violation: Service '{service_id}' is not confirmed as a trusted credential recipient for current version/endpoint. Refusing to forward user credentials."
                    )

                env = os.getenv("HUB_ENV", "development").lower()
                if env == "production" and urlparse(svc.endpoint_url).scheme.lower() != "https":
                    dur = round((time.time() - start_time) * 1000, 2)
                    err_text = f"rejected: insecure credential transport '{svc.endpoint_url}' in production"
                    logger.error("Blocked credential dispatch over non-HTTPS transport in production for service '%s'", service_id)
                    await _record_audit(err_text, dur)
                    raise PermissionError(
                        f"Security policy violation: Production mode requires HTTPS protected transport before dispatching personal credentials to '{service_id}'."
                    )

                existing_binding = await self.store.get_user_binding(user_id, svc.id)
                if existing_binding and existing_binding.status == "invalid":
                    dur = round((time.time() - start_time) * 1000, 2)
                    err_text = f"rejected: user credentials invalid for service '{service_id}'"
                    logger.warning(
                        "Blocked tool call due to invalid user credentials: user '%s', service '%s', tool '%s'",
                        user_id,
                        service_id,
                        tool_name,
                    )
                    await _record_audit(err_text, dur)
                    raise RuntimeError(
                        f"Service '{service_id}' credentials for user '{user_id}' are invalid or expired. Please re-bind credentials in Capability Portal."
                    )

                cred_res = await self.store.get_decrypted_credentials(user_id, svc.id)
                if not cred_res:
                    dur = round((time.time() - start_time) * 1000, 2)
                    err_text = f"rejected: missing required user credentials for service '{service_id}'"
                    logger.warning(
                        "Blocked tool call due to missing user credentials: user '%s', service '%s', tool '%s'",
                        user_id,
                        service_id,
                        tool_name,
                    )
                    await _record_audit(err_text, dur)
                    raise RuntimeError(
                        f"Service '{service_id}' requires personal credentials. User '{user_id}' has not configured credentials for this service. Please configure credentials in Capability Portal."
                    )
                decrypted_creds, cred_ver = cred_res

                credential_context = {
                    "user_id": user_id,
                    "service_id": svc.id,
                    "credential_version": cred_ver,
                    "credentials": decrypted_creds,
                }

        # 5. 执行下游调用 (前置拦截时下游调用次数严格为零)
        result_status = "success"
        cred_token = None
        if credential_context:
            cred_token = current_invocation_credential_cv.set(credential_context)
        try:
            result = await call_next(context)
            is_err = bool(getattr(result, "is_error", False) or getattr(result, "isError", False))
            parsed_payload: Optional[Dict[str, Any]] = None
            sc = getattr(result, "structured_content", None)
            if isinstance(sc, dict):
                parsed_payload = sc
            elif hasattr(result, "content") and result.content:
                first = result.content[0]
                text_val = getattr(first, "text", None)
                if isinstance(text_val, str):
                    try:
                        loaded = json.loads(text_val)
                        if isinstance(loaded, dict):
                            parsed_payload = loaded
                    except Exception:
                        parsed_payload = None

            err_code = parsed_payload.get("error_code") if isinstance(parsed_payload, dict) else None
            if err_code == "INVALID_CREDENTIALS":
                result_status = "rejected: invalid downstream credentials"
                if self.store and svc:
                    await self.store.update_downstream_status(svc.id, "available", None)
                    if credential_context:
                        await self.store.update_binding_status(user_id, svc.id, "invalid", "invalid")
            elif err_code == "DOWNSTREAM_UNAVAILABLE":
                result_status = "downstream_unavailable"
                if self.store and svc:
                    err_msg = str(parsed_payload.get("message") or "Downstream system unavailable")
                    await self.store.update_downstream_status(svc.id, "unavailable", err_msg)
            elif is_err:
                result_status = "tool_error"
            else:
                if self.store and svc:
                    await self.store.update_downstream_status(svc.id, "available", None)
                    if credential_context:
                        await self.store.update_binding_status(user_id, svc.id, "active", "verified")
            return result
        except Exception as exc:
            result_status = f"exception: {exc}"
            if self.store and svc:
                err_lower = str(exc).lower()
                if any(k in err_lower for k in ("connect", "timeout", "timed out", "unavailable", "refused", "unreachable", "502", "503", "504", "httpx")):
                    await self.store.update_downstream_status(svc.id, "unavailable", str(exc))
            raise
        finally:
            if cred_token is not None:
                current_invocation_credential_cv.reset(cred_token)
            if not audit_recorded:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                await _record_audit(result_status, duration_ms)
