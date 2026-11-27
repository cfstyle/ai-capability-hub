"""管理 REST API 路由

提供服务注册、查询、工具列表等管理接口。
所有路由需要 admin 认证（ADR-009）。
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from fastmcp import Client
from pydantic import BaseModel

from src.gateway.aggregator import HubAggregator
from src.gateway.plugin_manager import plugin_manager, PluginValidationError
from src.governance.middleware import desensitize_params
from src.registry.models import (
    CredentialTrustUpdate,
    InvocationLogItem,
    PermissionRequest,
    PermissionRequestReview,
    PermissionRequestStatus,
    RegisteredService,
    RegisteredTool,
    ServiceMetadataUpdate,
    ServiceRegistration,
    ServiceStatus,
    ToolPolicyUpdate,
    ToolRiskLevel,
)
from src.registry.store import RegistryStore

logger = logging.getLogger(__name__)

api_router = APIRouter(tags=["admin"])


# --- 依赖注入 ---


async def verify_admin(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
) -> str:
    """验证管理员身份 (ADR-009)

    优先支持受信任的管理员 JWT（带 hub:admin scope 且未被吊销），同时兼容 X-API-Key / X-Admin-Key。
    """
    from src.config import settings
    from src.governance.auth import verify_token

    config = getattr(request.app.state, "config", None)
    store = getattr(request.app.state, "store", None)
    expected_keys = {
        getattr(config, "admin_api_key", None),
        getattr(settings, "admin_api_key", None),
    }
    expected_keys.discard(None)
    expected_keys.discard("")

    provided_key = x_api_key or x_admin_key
    admin_identity: Optional[str] = None
    bearer_attempted = False

    if authorization and authorization.lower().startswith("bearer "):
        bearer_attempted = True
        bearer_val = authorization.split(" ", 1)[1].strip()
        try:
            payload = verify_token(bearer_val)
            if "hub:admin" in payload.scopes:
                if store is not None and await store.is_token_revoked(payload.sub, payload.iat):
                    raise HTTPException(status_code=401, detail="Admin token has been revoked")
                admin_identity = payload.sub
            else:
                raise HTTPException(status_code=403, detail="Insufficient permissions: hub:admin scope required")
        except HTTPException:
            raise
        except Exception:
            pass
        if not provided_key:
            provided_key = bearer_val

    if admin_identity:
        return admin_identity

    # 未走通 JWT 时：若仅携带了无效 Bearer 且系统未启用静态 Key，直接返回 401
    if not expected_keys:
        if bearer_attempted:
            raise HTTPException(status_code=401, detail="Invalid or untrusted admin bearer token")
        raise HTTPException(
            status_code=503,
            detail="Admin API key is not configured on server. Management requests are disabled.",
        )

    if not provided_key:
        raise HTTPException(status_code=401, detail="Missing admin authentication")

    if provided_key not in expected_keys:
        raise HTTPException(status_code=403, detail="Invalid admin API key")

    return request.headers.get("X-Admin-User") or "admin"


async def verify_internal_secret(
    request: Request,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
) -> None:
    """校验来自 RgOne 后端的内部服务调用密钥"""
    import os
    from hmac import compare_digest
    from src.config import settings

    config = getattr(request.app.state, "config", None)
    expected = (
        os.getenv("HUB_INTERNAL_SERVICE_SECRET")
        or getattr(config, "internal_service_secret", None)
        or getattr(settings, "internal_service_secret", None)
        or ""
    ).strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Internal service secret is not configured")
    if not x_internal_secret or not compare_digest(x_internal_secret.strip(), expected):
        raise HTTPException(status_code=403, detail="Invalid internal service secret")


def get_store(request: Request) -> RegistryStore:
    store = getattr(request.app.state, "store", None)
    if not store:
        raise HTTPException(status_code=503, detail="RegistryStore is not initialized")
    return store


def get_aggregator(request: Request) -> HubAggregator:
    aggregator = getattr(request.app.state, "aggregator", None)
    if not aggregator:
        raise HTTPException(status_code=503, detail="HubAggregator is not initialized")
    return aggregator


def infer_tool_risk(name: str, desc: str) -> tuple[ToolRiskLevel, bool]:
    """根据工具名称与描述自动推断风险等级 (ADR-005)"""
    lower = f"{name} {desc}".lower()
    if any(k in lower for k in ["delete", "drop", "destroy", "shutdown", "kill", "purge", "revoke"]):
        return ToolRiskLevel.L3, True
    if any(k in lower for k in ["send", "create", "update", "transfer", "submit", "pay", "write", "post"]):
        return ToolRiskLevel.L2, True
    if any(k in lower for k in ["draft", "temp", "calculate", "analyze", "estimate"]):
        return ToolRiskLevel.L1, False
    return ToolRiskLevel.L0, False


class UpdateServiceStatusRequest(BaseModel):
    """更新服务状态请求"""
    status: ServiceStatus


def validate_endpoint_url(url: str) -> None:
    """校验下游 MCP 服务地址的合法性与协议安全范围"""
    if not url:
        raise HTTPException(status_code=400, detail="Service endpoint URL cannot be empty")
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid URL scheme '{parsed.scheme}'. Only 'http' and 'https' are allowed for MCP services.",
        )
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid service endpoint URL: missing host")


_service_refresh_locks: Dict[str, asyncio.Lock] = {}
_refresh_lock_mutex = asyncio.Lock()


async def _get_service_lock(service_id: str) -> asyncio.Lock:
    async with _refresh_lock_mutex:
        if service_id not in _service_refresh_locks:
            _service_refresh_locks[service_id] = asyncio.Lock()
        return _service_refresh_locks[service_id]


async def discover_tools(endpoint_url: str, service_id: str) -> List[RegisteredTool]:
    """主动连接下游 MCP Server 拉取 tools/list 进行工具发现 (ADR-005)

    发现失败抛出异常，绝不静默返回空数组，避免误删目录。
    """
    validate_endpoint_url(endpoint_url)
    try:
        async with Client(endpoint_url) as client:
            tools = await client.list_tools()
            discovered = []
            for t in tools:
                name = t.name
                desc = t.description or ""
                # fastmcp 4.x / MCP SDK v2
                schema = getattr(t, "input_schema", {}) or getattr(t, "parameters", {}) or {}
                if hasattr(schema, "model_dump"):
                    schema = schema.model_dump()
                elif hasattr(schema, "dict"):
                    schema = schema.dict()

                risk_lvl, req_confirm = infer_tool_risk(name, desc)
                t_meta = getattr(t, "meta", None) or {}
                if not isinstance(t_meta, dict):
                    t_meta = {}
                declared_risk = t_meta.get("risk_level")
                if declared_risk in [ToolRiskLevel.L0, ToolRiskLevel.L1, ToolRiskLevel.L2, ToolRiskLevel.L3]:
                    risk_lvl = ToolRiskLevel(declared_risk)
                    req_confirm = risk_lvl in (ToolRiskLevel.L2, ToolRiskLevel.L3)
                has_explicit_creds = "requires_credentials" in t_meta
                req_creds = bool(t_meta.get("requires_credentials", False)) if has_explicit_creds else False
                req_creds_explicit = bool(t_meta.get("requires_credentials")) if has_explicit_creds else None

                discovered.append(
                    RegisteredTool(
                        service_id=service_id,
                        name=name,
                        description=desc,
                        input_schema=schema if isinstance(schema, dict) else {},
                        risk_level=risk_lvl,
                        requires_confirmation=req_confirm,
                        requires_credentials=req_creds,
                        requires_credentials_explicit=req_creds_explicit,
                    )
                )
            return discovered
    except Exception as exc:
        logger.warning("Tool discovery failed for %s (%s): %s", service_id, endpoint_url, exc)
        raise RuntimeError(f"Tool discovery failed for {service_id} at '{endpoint_url}': {exc}")



def _apply_manifest_tool_overrides(tools: List[RegisteredTool], manifest: Dict[str, Any]) -> None:
    """按声明优先级合并 manifest.json 工具元数据（manifest 显式声明 > MCP tool meta > 库内旧值）"""
    manifest_tool_map = {
        t["name"]: t for t in manifest.get("tools", []) if isinstance(t, dict) and "name" in t
    }
    for tool in tools:
        if tool.name in manifest_tool_map:
            m_tool = manifest_tool_map[tool.name]
            declared_risk = m_tool.get("risk_level")
            if declared_risk in [ToolRiskLevel.L0, ToolRiskLevel.L1, ToolRiskLevel.L2, ToolRiskLevel.L3]:
                tool.risk_level = ToolRiskLevel(declared_risk)
                if declared_risk in [ToolRiskLevel.L2, ToolRiskLevel.L3]:
                    tool.requires_confirmation = True
            if "requires_credentials" in m_tool:
                val = bool(m_tool.get("requires_credentials"))
                tool.requires_credentials = val
                tool.requires_credentials_explicit = val


def _load_service_manifest(service_id: str) -> Optional[Dict[str, Any]]:
    """读取已发布插件本地落地目录中的 manifest.json（若存在）"""
    import json
    manifest_path = plugin_manager.services_dir / service_id / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("Failed to parse manifest for %s: %s", service_id, exc)
        return None


# --- 插件自助发布路由 ---


@api_router.get(
    "/plugins/template/download",
    summary="下载标准 MCP 插件脚手架 ZIP 模板",
)
async def download_plugin_template(
    _admin: str = Depends(verify_admin),
):
    """供开发者一键下载符合规范的 demo 脚手架（包含 manifest.json, server.py, agent.md 等）"""
    try:
        buf = plugin_manager.generate_demo_template_zip()
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="python-mcp-demo.zip"'},
        )
    except Exception as exc:
        logger.exception("Failed to generate demo template zip: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@api_router.post(
    "/plugins/inspect",
    summary="预检上传的 MCP 插件压缩包",
)
async def inspect_plugin(
    file: UploadFile = File(..., description="MCP 插件 ZIP 压缩包"),
    _admin: str = Depends(verify_admin),
) -> Dict[str, Any]:
    """解析并校验上传的 ZIP 包，提取 manifest.json 和 server.py 信息供前端确认预览"""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="上传文件必须为 .zip 格式")

    content = await file.read()
    try:
        result = plugin_manager.inspect_plugin_zip(content)
        return result
    except PluginValidationError as pve:
        raise HTTPException(status_code=400, detail=str(pve))
    except Exception as exc:
        logger.exception("Unexpected error during plugin inspection: %s", exc)
        raise HTTPException(status_code=500, detail=f"解压预检失败: {exc}")


@api_router.post(
    "/plugins/publish",
    response_model=RegisteredService,
    summary="一键发布并上线 MCP 插件",
)
async def publish_plugin(
    request: Request,
    file: UploadFile = File(..., description="MCP 插件 ZIP 压缩包"),
    service_id: Optional[str] = Form(None, description="自定义覆盖 service_id"),
    name: Optional[str] = Form(None, description="自定义覆盖服务显示名称"),
    description: Optional[str] = Form(None, description="自定义覆盖服务描述"),
    owner: Optional[str] = Form(None, description="维护团队/负责人"),
    category: Optional[str] = Form("自研业务", description="业务分类"),
    _admin: str = Depends(verify_admin),
) -> RegisteredService:
    """一键解压、启动微服务、发现工具、持久化并动态挂载至 MCP Gateway"""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="上传文件必须为 .zip 格式")

    content = await file.read()
    try:
        inspect_info = plugin_manager.inspect_plugin_zip(content)
    except PluginValidationError as pve:
        raise HTTPException(status_code=400, detail=str(pve))

    target_service_id = service_id.strip() if service_id else inspect_info["service_id"]
    service_name = name.strip() if name else inspect_info["name"]
    service_desc = description.strip() if description else inspect_info["description"]
    service_owner = owner.strip() if owner else inspect_info["author"]
    manifest = inspect_info["manifest"]

    store = get_store(request)
    aggregator = get_aggregator(request)

    # 1. 解压到 services 目录
    try:
        target_dir, _ = plugin_manager.extract_plugin(content, target_service_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"解压落地失败: {exc}")

    # 2. 启动服务进程并等待健康检查
    try:
        endpoint_url, pid = await plugin_manager.start_service_process(target_service_id, target_dir)
    except Exception as exc:
        logger.exception("Failed to start plugin process for %s: %s", target_service_id, exc)
        raise HTTPException(status_code=500, detail=f"服务启动失败: {exc}")

    # 3. 构造注册元数据 (manifest 只能声明需要凭据，接收方默认不受信任，须由管理员独立确认)
    credential_schema = manifest.get("credential_schema")
    plugin_version = str(manifest.get("version") or "1.0.0").strip() or "1.0.0"
    reg = ServiceRegistration(
        service_id=target_service_id,
        name=service_name,
        description=service_desc,
        endpoint_url=endpoint_url,
        version=plugin_version,
        owner=service_owner,
        category=category or "自研业务",
        credential_schema=credential_schema,
        trusted_credential_recipient=False,
    )

    # 4. 注册持久化
    svc = await store.register_service(reg)

    # 5. 工具发现并持久化基线
    discovered_tools = await discover_tools(endpoint_url, target_service_id)

    # 结合 manifest.json 中声明的 risk_level 与 requires_credentials
    _apply_manifest_tool_overrides(discovered_tools, manifest)

    if discovered_tools:
        await store.save_tools(target_service_id, discovered_tools, preserve_policies=True)
        logger.info("Published plugin %s with %d discovered tools", target_service_id, len(discovered_tools))

    # 6. 动态挂载到 Gateway
    try:
        aggregator.mount_service(target_service_id, endpoint_url)
    except Exception as exc:
        logger.error("Failed to dynamically mount plugin %s: %s", target_service_id, exc)

    return svc


# --- 服务管理路由 ---


@api_router.post(
    "/services/register",
    response_model=RegisteredService,
    summary="注册新 MCP 服务",
)
async def register_service(
    registration: ServiceRegistration,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> RegisteredService:
    """注册新服务：执行连接探测、工具发现、基线快照入库与网关动态挂载"""
    validate_endpoint_url(registration.endpoint_url)
    # 凭据接收方默认不受信任，禁止通过注册载荷自声明可信
    registration.trusted_credential_recipient = False
    store = get_store(request)
    aggregator = get_aggregator(request)

    # 1. 持久化服务记录
    svc = await store.register_service(registration)

    # 2. 发现成功后再安全提交快照（即使首次未能连上也不导致崩溃或清空）
    try:
        tools = await discover_tools(registration.endpoint_url, registration.service_id)
        if tools:
            await store.save_tools(registration.service_id, tools, preserve_policies=True)
            logger.info("Discovered %d tools for service %s", len(tools), registration.service_id)
    except Exception as exc:
        logger.warning("Initial tool discovery for %s was not ready: %s", registration.service_id, exc)

    # 3. 动态挂载至 MCP 聚合网关
    try:
        aggregator.mount_service(registration.service_id, registration.endpoint_url)
    except Exception as exc:
        logger.error("Failed to dynamically mount service %s: %s", registration.service_id, exc)

    return svc


@api_router.get(
    "/services",
    response_model=List[RegisteredService],
    summary="列出已注册服务",
)
@api_router.get(
    "/servers",
    response_model=List[RegisteredService],
    summary="列出已注册服务 (alias)",
)
async def list_services(
    request: Request,
    status: Optional[ServiceStatus] = None,
    _admin: str = Depends(verify_admin),
) -> List[RegisteredService]:
    """列出所有已注册服务，支持状态过滤"""
    store = get_store(request)
    return await store.list_services(status=status)


@api_router.get(
    "/services/{service_id}",
    response_model=RegisteredService,
    summary="查询服务详情",
)
@api_router.get(
    "/servers/{service_id}",
    response_model=RegisteredService,
    summary="查询服务详情 (alias)",
)
async def get_service(
    service_id: str,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> RegisteredService:
    """查询指定服务详细信息"""
    store = get_store(request)
    svc = await store.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    return svc


@api_router.post(
    "/services/{service_id}/test",
    summary="测试服务连接",
)
@api_router.post(
    "/servers/{service_id}/test",
    summary="测试服务连接 (alias)",
)
async def test_service_connection(
    service_id: str,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> Dict[str, Any]:
    """测试指定服务的连接与可用性"""
    store = get_store(request)
    svc = await store.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    start_time = time.time()
    try:
        async with Client(svc.endpoint_url) as client:
            tools = await client.list_tools()
            duration_ms = round((time.time() - start_time) * 1000, 2)
            await store.update_downstream_status(service_id, "available", None)
            return {
                "success": True,
                "service_id": service_id,
                "endpoint_url": svc.endpoint_url,
                "latency_ms": duration_ms,
                "tools_count": len(tools),
                "message": f"连接正常，探测到 {len(tools)} 个能力工具 (耗时 {duration_ms}ms)",
            }
    except Exception as exc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.warning("Connection test failed for %s (%s): %s", service_id, svc.endpoint_url, exc)
        await store.update_downstream_status(service_id, "unavailable", str(exc))
        return {
            "success": False,
            "service_id": service_id,
            "endpoint_url": svc.endpoint_url,
            "latency_ms": duration_ms,
            "error": str(exc),
            "message": f"连接失败: {exc}",
        }


@api_router.post(
    "/services/{service_id}/refresh",
    summary="刷新工具定义",
)
async def refresh_service_tools(
    service_id: str,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> Dict[str, Any]:
    """重新连接远程 MCP Server 并刷新工具定义列表（串行化保护与安全快照比对）"""
    store = get_store(request)
    aggregator = get_aggregator(request)

    svc = await store.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    # 同一服务刷新串行化
    lock = await _get_service_lock(service_id)
    async with lock:
        try:
            tools = await discover_tools(svc.endpoint_url, service_id)
        except Exception as exc:
            logger.warning("Refresh tool discovery failed for %s: %s", service_id, exc)
            raise HTTPException(
                status_code=502,
                detail=f"Failed to refresh tools from upstream '{svc.endpoint_url}': {exc}. Existing tools and policies have been preserved.",
            )

        # 若存在落地 manifest.json，先合并其显式声明；未显式声明的工具凭据要求由 preserve_policies=True 兜底保留
        local_manifest = _load_service_manifest(service_id)
        if local_manifest:
            _apply_manifest_tool_overrides(tools, local_manifest)

        # 发现成功后再安全提交快照，保留此前管理员调整过的人工策略与已有凭据声明
        await store.save_tools(service_id, tools, preserve_policies=True)

        # 重新挂载服务代理
        try:
            aggregator.mount_service(service_id, svc.endpoint_url)
        except Exception as exc:
            logger.warning("Refresh remount for %s: %s", service_id, exc)

        return {
            "service_id": service_id,
            "tools_discovered": len(tools),
            "status": "refreshed",
        }


@api_router.put(
    "/services/{service_id}/status",
    response_model=RegisteredService,
    summary="更新服务状态",
)
async def update_service_status(
    service_id: str,
    payload: UpdateServiceStatusRequest,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> RegisteredService:
    """更新服务状态（启用/停用/降级）"""
    store = get_store(request)
    svc = await store.update_service_status(service_id, payload.status)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    return svc


@api_router.put(
    "/services/{service_id}/credential-trust",
    response_model=RegisteredService,
    summary="管理员独立确认或撤销个人凭据接收方信任状态",
)
@api_router.post(
    "/services/{service_id}/credential-trust",
    response_model=RegisteredService,
    summary="管理员独立确认或撤销个人凭据接收方信任状态 (POST alias)",
)
@api_router.put(
    "/servers/{service_id}/credential-trust",
    response_model=RegisteredService,
    summary="管理员独立确认或撤销个人凭据接收方信任状态 (alias)",
)
async def update_service_credential_trust(
    service_id: str,
    payload: CredentialTrustUpdate,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> RegisteredService:
    """由管理员独立确认某服务是否可接收个人凭据，并绑定其当前版本与目标地址"""
    store = get_store(request)
    svc = await store.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    if payload.trusted:
        env = os.getenv("HUB_ENV", "development").lower()
        scheme = urlparse(svc.endpoint_url).scheme.lower()
        if env == "production" and scheme != "https":
            raise HTTPException(
                status_code=400,
                detail="生产环境强制受保护传输：仅允许对 https:// 端点的服务确认个人凭据接收方信任。",
            )

    updated = await store.confirm_credential_trust(service_id, payload.trusted, confirmed_by=_admin)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    return updated


@api_router.patch(
    "/services/{service_id}",
    response_model=RegisteredService,
    summary="更新服务元数据",
)
@api_router.patch(
    "/servers/{service_id}",
    response_model=RegisteredService,
    summary="更新服务元数据 (alias)",
)
async def update_service_metadata(
    service_id: str,
    payload: ServiceMetadataUpdate,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> RegisteredService:
    """更新服务显示名称、业务描述、维护人元数据"""
    store = get_store(request)
    svc = await store.update_service_metadata(
        service_id=service_id,
        name=payload.name,
        description=payload.description,
        owner=payload.owner,
        category=payload.category,
        auth_mode=payload.auth_mode,
        auth_label=payload.auth_label,
        auth_guide=payload.auth_guide,
        auth_entry_url=payload.auth_entry_url,
        usage_examples=payload.usage_examples,
    )
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    return svc



@api_router.get(
    "/tools",
    response_model=List[RegisteredTool],
    summary="列出所有工具",
)
async def list_tools(
    request: Request,
    service_id: Optional[str] = None,
    _admin: str = Depends(verify_admin),
) -> List[RegisteredTool]:
    """列出所有已注册工具，支持按服务 ID 过滤"""
    store = get_store(request)
    return await store.list_tools(service_id=service_id)


class ToolTestRequest(BaseModel):
    """工具在线测试入参"""
    arguments: Dict[str, Any] = {}


@api_router.get(
    "/tools/{tool_id}",
    response_model=RegisteredTool,
    summary="查询工具详情",
)
async def get_tool_detail(
    tool_id: str,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> RegisteredTool:
    """根据 ID 或命名空间名称查询工具详情"""
    store = get_store(request)
    if "__" in tool_id:
        tool = await store.get_tool_by_namespace_name(tool_id)
        if tool:
            return tool
    all_tools = await store.list_tools()
    for t in all_tools:
        if t.id == tool_id or t.name == tool_id or f"{t.service_id}__{t.name}" == tool_id:
            return t
    raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")


@api_router.patch(
    "/tools/{tool_id}/policy",
    response_model=RegisteredTool,
    summary="修改工具治理策略",
)
async def update_tool_policy(
    tool_id: str,
    payload: ToolPolicyUpdate,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> RegisteredTool:
    """修改工具风险等级（L0-L3）与人工确认规则"""
    store = get_store(request)
    tool = await store.update_tool_policy(
        tool_id=tool_id,
        risk_level=payload.risk_level,
        requires_confirmation=payload.requires_confirmation,
    )
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    return tool


@api_router.post(
    "/tools/{tool_id}/test",
    summary="在线受控测试工具调用",
)
async def test_tool_call(
    tool_id: str,
    payload: ToolTestRequest,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> Dict[str, Any]:
    """通过 Hub 调用下游 MCP Server 执行工具受控测试"""
    store = get_store(request)
    start_time = time.time()
    user_id = _admin
    client_id = "admin-debugger"
    clean_params = desensitize_params(payload.arguments)

    # 1. 精确查找工具
    tool = None
    if "__" in tool_id:
        tool = await store.get_tool_by_namespace_name(tool_id)
    if not tool:
        all_tools = await store.list_tools()
        for t in all_tools:
            if (
                t.id == tool_id
                or t.namespace_name == tool_id
                or f"{t.service_id}__{t.name}" == tool_id
                or f"{t.service_id}_{t.name}" == tool_id
                or t.name == tool_id
            ):
                tool = t
                break

    if not tool:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        await store.save_invocation_log({
            "user_id": user_id,
            "client_id": client_id,
            "tool_name": tool_id,
            "service_id": "unknown",
            "params_summary": clean_params,
            "result_status": f"rejected: tool '{tool_id}' not found",
            "duration_ms": duration_ms,
        })
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

    # 2. 检查所属服务状态
    svc = await store.get_service(tool.service_id)
    if not svc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        await store.save_invocation_log({
            "user_id": user_id,
            "client_id": client_id,
            "tool_name": tool.id,
            "service_id": tool.service_id,
            "params_summary": clean_params,
            "result_status": f"rejected: service '{tool.service_id}' not found",
            "duration_ms": duration_ms,
        })
        raise HTTPException(status_code=404, detail=f"Service '{tool.service_id}' not found")

    if svc.status != ServiceStatus.ACTIVE:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        await store.save_invocation_log({
            "user_id": user_id,
            "client_id": client_id,
            "tool_name": tool.id,
            "service_id": tool.service_id,
            "params_summary": clean_params,
            "result_status": f"rejected: service '{tool.service_id}' is {svc.status.value}",
            "duration_ms": duration_ms,
        })
        raise HTTPException(
            status_code=403,
            detail=f"Service '{tool.service_id}' is currently {svc.status.value}. Debug test call is blocked.",
        )

    # 3. 执行测试调用下游
    try:
        async with Client(svc.endpoint_url) as client:
            res = await client.call_tool(tool.name, payload.arguments)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            content_list = []
            if hasattr(res, "content"):
                for c in res.content:
                    if hasattr(c, "text"):
                        content_list.append(c.text)
                    elif hasattr(c, "model_dump"):
                        content_list.append(c.model_dump())
                    else:
                        content_list.append(str(c))
            elif hasattr(res, "model_dump"):
                content_list = res.model_dump()
            else:
                content_list = str(res)

            is_error = getattr(res, "isError", False)
            status_str = "tool_error" if is_error else "success"
            await store.save_invocation_log({
                "user_id": user_id,
                "client_id": client_id,
                "tool_name": tool.id,
                "service_id": tool.service_id,
                "params_summary": clean_params,
                "result_status": status_str,
                "duration_ms": duration_ms,
            })
            return {
                "tool_name": tool.name,
                "service_id": tool.service_id,
                "status": status_str,
                "duration_ms": duration_ms,
                "result": content_list,
            }
    except Exception as exc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.warning("Tool test execution error for %s: %s", tool_id, exc)
        await store.save_invocation_log({
            "user_id": user_id,
            "client_id": client_id,
            "tool_name": tool.id,
            "service_id": tool.service_id,
            "params_summary": clean_params,
            "result_status": f"exception: {exc}",
            "duration_ms": duration_ms,
        })
        return {
            "tool_name": tool.name,
            "service_id": tool.service_id,
            "status": "exception",
            "duration_ms": duration_ms,
            "error": str(exc),
        }


# --- 仪表盘、系统与审计接口 ---


@api_router.get(
    "/dashboard/summary",
    summary="首页统计概览",
)
async def get_dashboard_summary(
    request: Request,
    _admin: str = Depends(verify_admin),
) -> Dict[str, Any]:
    """获取管理端首页运行总览指标（与门户概览共享真实调用统计）"""
    store = get_store(request)
    services = await store.list_services()
    tools = await store.list_tools()
    inv_summary = await store.get_invocation_summary()
    portal_ov = await store.get_portal_overview()

    active = sum(1 for s in services if s.status == ServiceStatus.ACTIVE)
    inactive = sum(1 for s in services if s.status == ServiceStatus.INACTIVE)
    degraded = sum(1 for s in services if s.status == ServiceStatus.DEGRADED)

    return {
        "servers_total": len(services),
        "servers_active": active,
        "servers_inactive": inactive,
        "servers_degraded": degraded,
        "tools_total": len(tools),
        "calls_total": inv_summary["calls_total"],
        "calls_success": inv_summary["calls_success"],
        "calls_failed": inv_summary["calls_failed"],
        "health_rate": portal_ov.health_rate,
        "daily_trends": [t.model_dump() for t in portal_ov.daily_trends],
    }


class UserRevocationRequest(BaseModel):
    """员工凭证吊销/恢复请求"""
    reason: str = ""
    revoked_before: Optional[int] = None


@api_router.post(
    "/internal/users/{emp_no}/revoke",
    summary="内部接口：停用员工并吊销此前签发的所有 JWT/MCP Token",
)
async def internal_revoke_user(
    emp_no: str,
    request: Request,
    body: Optional[UserRevocationRequest] = None,
    _: None = Depends(verify_internal_secret),
) -> Dict[str, Any]:
    """停用员工时调用：立即封禁其 Web JWT 与所有历史 ide-client 长效 MCP Token"""
    store = get_store(request)
    now_ts = int(time.time())
    cutoff = body.revoked_before if (body and body.revoked_before is not None) else now_ts
    reason = body.reason if body else "employee_disabled"
    return await store.set_user_revocation(
        emp_no=emp_no.strip(),
        is_active=False,
        revoked_before=cutoff,
        reason=reason,
    )


@api_router.post(
    "/internal/users/{emp_no}/restore",
    summary="内部接口：复职恢复员工访问状态（历史旧 Token 仍维持吊销）",
)
async def internal_restore_user(
    emp_no: str,
    request: Request,
    body: Optional[UserRevocationRequest] = None,
    _: None = Depends(verify_internal_secret),
) -> Dict[str, Any]:
    """员工复职时调用：恢复账号可用，但保留原有 revoked_before 水位线以防止停用前旧 Token 复活"""
    store = get_store(request)
    reason = body.reason if body else "employee_restored"
    return await store.set_user_revocation(
        emp_no=emp_no.strip(),
        is_active=True,
        revoked_before=None,
        reason=reason,
    )


@api_router.get(
    "/system/status",
    summary="系统运行状态",
)
async def get_system_status(
    request: Request,
    _admin: str = Depends(verify_admin),
) -> Dict[str, Any]:
    """获取 Hub Core 运行状态与基础配置"""
    config = getattr(request.app.state, "config", None)
    store = get_store(request)
    services = await store.list_services()

    return {
        "hub_name": getattr(config, "hub_name", "AI Capability Hub") if config else "AI Capability Hub",
        "hub_version": getattr(config, "hub_version", "0.2.2") if config else "0.2.2",
        "status": "ready",
        "database": getattr(config, "database_url", "sqlite:///data/hub.db") if config else "sqlite:///data/hub.db",
        "mcp_endpoint": getattr(config, "mcp_endpoint_path", "/mcp") if config else "/mcp",
        "upstream_services_count": len(services),
    }


@api_router.get(
    "/audit-logs",
    summary="调用审计日志",
)
async def list_audit_logs(
    request: Request,
    service_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    _admin: str = Depends(verify_admin),
) -> Dict[str, Any]:
    """查询工具调用审计日志（支持分页与多维过滤）"""
    store = get_store(request)
    items, total = await store.list_invocation_logs(
        service_id=service_id,
        tool_name=tool_name,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "items": items,
        "total": total,
    }


@api_router.get(
    "/admin/permission-requests",
    response_model=List[PermissionRequest],
    summary="管理端：查询所有功能权限申请单",
)
async def list_admin_permission_requests(
    request: Request,
    user_id: Optional[str] = None,
    status: Optional[PermissionRequestStatus] = None,
    _admin: str = Depends(verify_admin),
) -> List[PermissionRequest]:
    """管理端查询权限申请单列表"""
    store = get_store(request)
    return await store.list_permission_requests(user_id=user_id, status=status)


@api_router.post(
    "/admin/permission-requests/{request_id}/review",
    response_model=PermissionRequest,
    summary="管理端：审批功能权限申请",
)
async def review_admin_permission_request(
    request_id: str,
    body: PermissionRequestReview,
    request: Request,
    _admin: str = Depends(verify_admin),
) -> PermissionRequest:
    """审批权限申请（同意或驳回）；同意时自动将对应工具赋予该用户并在 Gateway 动态生效"""
    store = get_store(request)
    body.reviewer = body.reviewer or _admin
    try:
        updated = await store.review_permission_request(request_id, body)
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))
    if not updated:
        raise HTTPException(status_code=404, detail="Permission request not found")
    return updated

