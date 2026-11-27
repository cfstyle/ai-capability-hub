"""面向非开发者的公开门户 (Capability Portal) REST API 路由

提供免登录访问的能力概览、脱敏能力卡片、完整接入详情。
安全红线：
1. 纯只读，严禁提供任何写操作接口。
2. 严禁暴露真实内网 endpoint_url 与负责人隐私信息。
3. 严格过滤非 active 状态服务。
4. 数据全部真实计算，拒绝模拟假数据。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.governance.auth import ADMIN_SCOPES, USER_SCOPES, create_access_token, get_current_user
from src.registry.models import (
    PermissionRequest,
    PermissionRequestCreate,
    PermissionRequestStatus,
    PortalCapabilityCard,
    PortalCapabilityDetail,
    PortalOverview,
    UserMcpDetail,
    UserServiceBinding,
    UserServiceBindingUpdate,
)
from src.registry.store import RegistryStore

logger = logging.getLogger(__name__)

portal_router = APIRouter(prefix="/portal", tags=["portal"])


def _get_store(request: Request) -> RegistryStore:
    store = getattr(request.app.state, "store", None)
    if not store:
        raise HTTPException(status_code=503, detail="RegistryStore is not initialized")
    return store


def _resolve_public_mcp_url(request: Request) -> str:
    """计算对外暴露的统一 MCP Gateway 地址 (Streamable HTTP 端点)"""
    config = getattr(request.app.state, "config", None)
    configured_url = getattr(config, "public_mcp_url", None)
    if configured_url:
        return configured_url.rstrip("/")

    # 根据请求头动态推导，支持反向代理头
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or f"{request.url.hostname}:{request.url.port}"
    )
    mcp_path = getattr(config, "mcp_endpoint_path", "/mcp") if config else "/mcp"
    if not mcp_path.startswith("/"):
        mcp_path = "/" + mcp_path

    return f"{proto}://{host}{mcp_path}"


@portal_router.get(
    "/overview",
    response_model=PortalOverview,
    summary="获取门户全局概览与真实统计趋势",
)
async def get_portal_overview(request: Request) -> PortalOverview:
    """获取门户概览统计：已发布服务数、工具总数、真实累计调用量、近 7 日每日调用趋势与健康率"""
    store = _get_store(request)
    return await store.get_portal_overview()


@portal_router.get(
    "/capabilities",
    response_model=List[PortalCapabilityCard],
    summary="获取已发布公开能力列表（脱敏）",
)
async def list_portal_capabilities(
    request: Request,
    q: Optional[str] = Query(None, description="搜索关键词（匹配服务名称、业务说明、工具名称与描述）"),
    category: Optional[str] = Query(None, description="分类标签过滤"),
    sort_by: str = Query("popular", description="排序方式: popular (热门调用), recent_active (最近活跃), newest (最新上线), name (服务名称)"),
) -> List[PortalCapabilityCard]:
    """获取脱敏后的已发布能力卡片列表，支持分类筛选、关键字搜索与真实热度排序"""
    store = _get_store(request)
    return await store.list_portal_capabilities(q=q, category=category, sort_by=sort_by)


@portal_router.get(
    "/capabilities/{capability_id}",
    response_model=PortalCapabilityDetail,
    summary="获取单个能力的完整公开接入详情",
)
async def get_portal_capability_detail(
    capability_id: str,
    request: Request,
) -> PortalCapabilityDetail:
    """获取单个已发布能力完整详情：包含工具清单、真实 7 日调用趋势、统一 MCP Gateway 地址与认证说明"""
    store = _get_store(request)
    public_gateway_url = _resolve_public_mcp_url(request)
    detail = await store.get_portal_capability_detail(capability_id, public_gateway_url)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail=f"Capability '{capability_id}' not found or not published/active",
        )
    return detail


@portal_router.get(
    "/docs/developer-guide",
    summary="获取业务 MCP 插件开发规范与手册",
)
async def get_developer_guide() -> dict:
    """读取并返回 MCP 插件开发规范 Markdown 内容，供公开门户及管理端展示"""
    guide_path = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "MCP插件开发与发布规范.md"
    if not guide_path.exists():
        guide_path = Path("/app/docs/MCP插件开发与发布规范.md")

    if guide_path.exists():
        return {"content": guide_path.read_text(encoding="utf-8")}

    return {"content": "# MCP 插件开发与发布规范\n\n文档准备中..."}


class PortalLoginRequest(BaseModel):
    user_id: str = Field(..., description="企业工号")
    user_name: Optional[str] = Field(default=None, description="员工姓名")
    password: Optional[str] = Field(default=None, description="登录凭据")


class PortalLoginResponse(BaseModel):
    user_id: str
    user_name: str
    role: str
    token: str


@portal_router.post(
    "/auth/login",
    response_model=PortalLoginResponse,
    summary="企业用户工号凭据认证登录，换发安全签名 Token",
)
async def portal_auth_login(body: PortalLoginRequest) -> PortalLoginResponse:
    """提供企业员工凭据登录入口，生产模式强制禁用演示自报工号，开发/测试模式签发带真实 sub 的 JWT"""
    import os
    env = os.getenv("HUB_ENV", "development").lower()
    if env == "production":
        raise HTTPException(
            status_code=403,
            detail="生产模式已禁用演示工号快速登录。生产环境下必须接入企业统一身份认证源（SSO/OAuth2/OIDC），严禁在未接通受信任身份源时托管真实员工凭据。",
        )

    cleaned_uid = body.user_id.strip()
    if not cleaned_uid or cleaned_uid.lower() == "guest":
        raise HTTPException(status_code=400, detail="工号不能为空或为 guest")

    role = "admin" if (cleaned_uid.lower() == "admin" or cleaned_uid.lower().startswith("admin_")) else "user"
    scopes = ADMIN_SCOPES.copy() if role == "admin" else USER_SCOPES.copy()

    token = create_access_token(user_id=cleaned_uid, client_id="portal-web", scopes=scopes)

    return PortalLoginResponse(
        user_id=cleaned_uid,
        user_name=body.user_name.strip() if body.user_name else cleaned_uid,
        role=role,
        token=token,
    )


@portal_router.get(
    "/my-config",
    summary="获取当前用户的客户端一键接入配置与 Token",
)
async def get_portal_my_config(
    request: Request,
    user_id: Optional[str] = Query(None, description="[过渡期参数] 客户端自报工号，不参与主体选择"),
    user_name: Optional[str] = Query(None, description="[过渡期参数] 客户端自报姓名"),
) -> dict:
    """为用户生成 MCP 客户端接入配置。严格从服务端已验证身份上下文提取 sub。"""
    ctx_user = get_current_user()
    if ctx_user and ctx_user.sub and ctx_user.sub.lower() != "guest":
        effective_user_id = ctx_user.sub
        effective_user_name = ctx_user.name or effective_user_id
        is_guest = False
        token = create_access_token(user_id=effective_user_id, client_id="ide-client")
    else:
        effective_user_id = "guest"
        effective_user_name = "guest"
        is_guest = True
        token = ""

    public_mcp_url = _resolve_public_mcp_url(request)

    # 规范：客户端配置模板仅在 Authorization 请求头携带令牌，移除 URL 中重复的 ?token=...
    return {
        "user_id": effective_user_id,
        "user_name": effective_user_name,
        "is_guest": is_guest,
        "token": token,
        "guest_token": "",
        "gateway_url": public_mcp_url,
        "config_templates": {
            "cursor": {
                "mcpServers": {
                    "ai-capability-hub": {
                        "url": public_mcp_url,
                        "headers": {
                            "Authorization": f"Bearer {token}"
                        } if not is_guest else {}
                    }
                }
            },
            "claude": {
                "mcpServers": {
                    "ai-capability-hub": {
                        "url": public_mcp_url,
                        "headers": {
                            "Authorization": f"Bearer {token}"
                        } if not is_guest else {}
                    }
                }
            }
        }
    }


@portal_router.get(
    "/my-grants",
    summary="查询当前用户已开通/已授权的工具 ID 列表",
)
async def get_portal_my_grants(
    request: Request,
    user_id: Optional[str] = Query(None, description="[过渡期兼容参数] 查询以已验证主体为准"),
) -> dict:
    """返回当前已验证用户在所有 MCP 服务下已获得的非 L0 工具授权列表。查询条件强制取当前已验证主体。"""
    store = _get_store(request)
    ctx_user = get_current_user()
    if not ctx_user or not ctx_user.sub or ctx_user.sub.lower() == "guest":
        return {
            "user_id": "guest",
            "granted_tool_ids": [],
        }

    effective_user_id = ctx_user.sub
    granted_tool_ids = await store.get_user_granted_tool_ids(effective_user_id)
    return {
        "user_id": effective_user_id,
        "granted_tool_ids": granted_tool_ids,
    }


@portal_router.post(
    "/permission-requests",
    response_model=PermissionRequest,
    summary="用户提交工具功能权限开通申请",
)
async def create_portal_permission_request(
    body: PermissionRequestCreate,
    request: Request,
) -> PermissionRequest:
    """用户提交权限申请单。申请人必须来自服务端已验证的当前主体。"""
    store = _get_store(request)
    ctx_user = get_current_user()
    if not ctx_user or not ctx_user.sub or ctx_user.sub.lower() == "guest":
        raise HTTPException(status_code=401, detail="请先登录企业工号以提交权限申请")

    # 强制覆盖申请人工号为服务端已验证的主体，杜绝篡改伪造他人名义申请
    body.user_id = ctx_user.sub
    return await store.create_permission_request(body)


@portal_router.get(
    "/my-requests",
    response_model=List[PermissionRequest],
    summary="查询当前用户的权限申请历史",
)
async def list_portal_my_requests(
    request: Request,
    user_id: Optional[str] = Query(None, description="[过渡期兼容参数] 查询以已验证主体为准"),
) -> List[PermissionRequest]:
    """查询用户的申请单记录。查询条件强制取当前已验证主体。"""
    store = _get_store(request)
    ctx_user = get_current_user()
    if not ctx_user or not ctx_user.sub or ctx_user.sub.lower() == "guest":
        return []

    return await store.list_permission_requests(user_id=ctx_user.sub)


@portal_router.get(
    "/my-mcps",
    response_model=List[UserMcpDetail],
    summary="查询当前用户添加与授权的所有 MCP 服务概况",
)
async def get_portal_my_mcps(
    request: Request,
    probe: bool = Query(False, description="是否主动探测下游服务 /healthz 可达性"),
) -> List[UserMcpDetail]:
    """聚合返回当前用户添加的 MCP：已获批工具、待审工具、绑定的业务账号及凭据与下游可达状态。"""
    store = _get_store(request)
    ctx_user = get_current_user()
    if not ctx_user or not ctx_user.sub or ctx_user.sub.lower() == "guest":
        return []

    summary_items = await store.get_user_mcp_summary(ctx_user.sub)
    if probe and summary_items:
        import httpx
        from urllib.parse import urlparse

        async with httpx.AsyncClient(trust_env=False, timeout=1.5) as client:
            for item in summary_items:
                if item.get("service_status") != "active":
                    item["downstream_status"] = "unavailable"
                    continue
                ep = item.get("endpoint_url") or ""
                parsed = urlparse(ep)
                if not parsed.scheme or not parsed.netloc:
                    continue
                health_url = f"{parsed.scheme}://{parsed.netloc}/healthz"
                try:
                    resp = await client.get(health_url)
                    if resp.status_code < 400:
                        await store.update_downstream_status(item["service_id"], "available", None)
                        item["downstream_status"] = "available"
                        item["downstream_error"] = None
                    else:
                        err = f"HTTP {resp.status_code}"
                        await store.update_downstream_status(item["service_id"], "unavailable", err)
                        item["downstream_status"] = "unavailable"
                        item["downstream_error"] = err
                except Exception as exc:
                    await store.update_downstream_status(item["service_id"], "unavailable", str(exc))
                    item["downstream_status"] = "unavailable"
                    item["downstream_error"] = str(exc)

    return summary_items


@portal_router.post(
    "/my-mcps/{service_id}/binding",
    response_model=UserServiceBinding,
    summary="绑定或更新个人在特定 MCP 服务下的业务凭据",
)
async def update_portal_service_binding(
    service_id: str,
    body: UserServiceBindingUpdate,
    request: Request,
) -> UserServiceBinding:
    """用户保存/更新自己的业务账号与密码。保密字段加密存储，绝不回显密码明文。"""
    store = _get_store(request)
    ctx_user = get_current_user()
    if not ctx_user or not ctx_user.sub or ctx_user.sub.lower() == "guest":
        raise HTTPException(status_code=401, detail="请先登录企业工号")

    svc = await store.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    if not svc.credential_schema or not svc.credential_schema.enabled:
        raise HTTPException(status_code=400, detail=f"Service '{service_id}' does not require personal credentials")

    binding = await store.save_user_binding(
        user_id=ctx_user.sub,
        service_id=service_id,
        credentials=body.credentials,
        credential_schema=svc.credential_schema,
    )
    return binding


@portal_router.delete(
    "/my-mcps/{service_id}/binding",
    summary="解绑个人在特定 MCP 服务下的业务凭据",
)
async def unbind_portal_service_binding(
    service_id: str,
    request: Request,
) -> dict:
    """解绑用户的业务凭据。状态置为 unbound 并递增版本号，后续调用立即阻止。保留已获批工具授权。"""
    store = _get_store(request)
    ctx_user = get_current_user()
    if not ctx_user or not ctx_user.sub or ctx_user.sub.lower() == "guest":
        raise HTTPException(status_code=401, detail="请先登录企业工号")

    success = await store.unbind_user_service(user_id=ctx_user.sub, service_id=service_id)
    return {"status": "ok", "service_id": service_id, "unbound": success}


