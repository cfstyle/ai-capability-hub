"""认证与授权模块

MVP 阶段使用 JWT（python-jose）进行 token 验签。
后续可接入企业 IdP（OAuth2 / OIDC）。
"""

from __future__ import annotations

import contextvars
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from jose import JWTError, jwt
except ImportError:
    try:
        import jwt
        JWTError = getattr(jwt, "PyJWTError", Exception)
    except ImportError:
        jwt = None  # type: ignore
        JWTError = Exception
from pydantic import BaseModel, Field

from src.config import DEV_MCP_JWT_DEFAULT, load_config

logger = logging.getLogger(__name__)

# --- 权限范围常量 ---
ADMIN_SCOPES: List[str] = [
    "hub:admin",
    "hub:services:write",
    "hub:services:read",
    "hub:tools:call",
]

USER_SCOPES: List[str] = [
    "hub:services:read",
    "hub:tools:call",
]

_JWT_ALGORITHM = "HS256"


class TokenPayload(BaseModel):
    """JWT Token 解析后的载荷"""

    sub: str = Field(..., description="用户 ID")
    client_id: str = Field(default="", description="客户端应用 ID")
    scopes: List[str] = Field(default_factory=list, description="授权范围列表")
    exp: int = Field(default=2147483647, description="过期时间戳（Unix epoch）")
    iat: int = Field(default=0, description="签发时间戳（Unix epoch）")
    iss: str = Field(default="", description="签发者标识")
    name: str = Field(default="", description="用户显示姓名")


current_user_cv: contextvars.ContextVar[Optional[TokenPayload]] = contextvars.ContextVar(
    "current_user_cv", default=None
)


def get_current_user() -> Optional[TokenPayload]:
    """获取当前请求上下文中的用户身份，默认为 guest"""
    return current_user_cv.get()


def set_current_user(user: Optional[TokenPayload]) -> None:
    """设置当前请求上下文中的用户身份"""
    current_user_cv.set(user)


def _get_auth_settings() -> Dict[str, Any]:
    """读取当前 JWT 鉴权配置，优先响应环境变量（兼容运行时 monkeypatch 测试）"""
    cfg = load_config()
    hub_env = (cfg.hub_env or "development").strip().lower()
    mcp_secret = os.getenv("HUB_MCP_JWT_SECRET")
    if mcp_secret is None:
        mcp_secret = cfg.mcp_jwt_secret
    rgone_secret = os.getenv("HUB_RGONE_JWT_SECRET")
    if rgone_secret is None:
        rgone_secret = cfg.rgone_jwt_secret
    hub_issuer = (os.getenv("HUB_JWT_ISSUER") or cfg.hub_jwt_issuer or "ai-capability-hub").strip()
    rgone_issuer = (os.getenv("HUB_RGONE_JWT_ISSUER") or cfg.rgone_jwt_issuer or "rgone").strip()
    trust_env = os.getenv("HUB_TRUST_RGONE_ADMIN_JWT")
    if trust_env is not None:
        trust_rgone_admin = trust_env.strip().lower() in ("1", "true", "yes", "on")
    else:
        trust_rgone_admin = cfg.trust_rgone_admin_jwt

    if mcp_secret and rgone_secret and mcp_secret == rgone_secret:
        raise ValueError("HUB_MCP_JWT_SECRET and HUB_RGONE_JWT_SECRET must not be identical")
    if hub_env == "production" and (not mcp_secret or mcp_secret == DEV_MCP_JWT_DEFAULT):
        raise ValueError("HUB_MCP_JWT_SECRET must be set to a non-default secret in production")

    return {
        "hub_env": hub_env,
        "mcp_secret": mcp_secret,
        "rgone_secret": rgone_secret,
        "hub_issuer": hub_issuer,
        "rgone_issuer": rgone_issuer,
        "trust_rgone_admin": trust_rgone_admin,
    }


def _read_unverified_claims(token: str) -> Dict[str, Any]:
    """安全提取未验签 JWT Claims 用于按 iss 路由密钥"""
    if hasattr(jwt, "get_unverified_claims"):
        return jwt.get_unverified_claims(token)
    return jwt.decode(token, "", options={"verify_signature": False, "verify_exp": False})


def create_access_token(
    user_id: str,
    client_id: str = "ide-client",
    scopes: Optional[List[str]] = None,
    expires_delta_days: int = 30,
) -> str:
    """为指定用户和客户端签发带 iss 标识的 Hub JWT 访问令牌"""
    if scopes is None:
        scopes = USER_SCOPES.copy()

    auth_cfg = _get_auth_settings()
    now = datetime.now(timezone.utc)
    iat = int(now.timestamp())
    exp = int((now + timedelta(days=expires_delta_days)).timestamp())
    payload = {
        "sub": user_id,
        "iss": auth_cfg["hub_issuer"],
        "client_id": client_id,
        "scopes": scopes,
        "exp": exp,
        "iat": iat,
    }
    encoded = jwt.encode(payload, auth_cfg["mcp_secret"], algorithm=_JWT_ALGORITHM)
    if isinstance(encoded, bytes):
        return encoded.decode("utf-8")
    return encoded


def verify_token(token: str) -> TokenPayload:
    """按 iss 严格路由并验证 JWT Token，映射统一 TokenPayload。

    - iss == hub_jwt_issuer ("ai-capability-hub"): 使用 mcp_jwt_secret 验签
    - iss == rgone_jwt_issuer ("rgone"): 使用 rgone_jwt_secret 验签并按 role 严格映射 scopes
    - 其他或缺失 iss: 直接拒绝，禁止盲试双密钥
    """
    try:
        unverified = _read_unverified_claims(token)
        iss = str(unverified.get("iss") or "").strip()
        if not iss:
            raise ValueError("Missing token issuer (iss)")

        auth_cfg = _get_auth_settings()

        if iss == auth_cfg["hub_issuer"]:
            payload = jwt.decode(
                token,
                auth_cfg["mcp_secret"],
                algorithms=[_JWT_ALGORITHM],
            )
            sub = str(payload.get("sub") or "").strip()
            if not sub:
                raise ValueError("Missing token subject (sub)")
            return TokenPayload(
                sub=sub,
                client_id=str(payload.get("client_id") or ""),
                scopes=list(payload.get("scopes") or []),
                exp=int(payload.get("exp") or 0),
                iat=int(payload.get("iat") or 0),
                iss=iss,
                name=str(payload.get("name") or ""),
            )

        if iss == auth_cfg["rgone_issuer"]:
            rgone_secret = auth_cfg["rgone_secret"]
            if not rgone_secret:
                raise ValueError("RgOne JWT secret is not configured")
            if auth_cfg["hub_env"] == "production" and rgone_secret in (
                DEV_MCP_JWT_DEFAULT,
                "super_secret_jwt_key_for_rgone_portal_2026",
            ):
                raise ValueError("RgOne JWT secret must not use default development key in production")

            payload = jwt.decode(
                token,
                rgone_secret,
                algorithms=[_JWT_ALGORITHM],
            )
            sub = str(payload.get("sub") or "").strip()
            if not sub:
                raise ValueError("Missing token subject (sub)")
            role = str(payload.get("role") or "").strip().lower()
            if role == "employee":
                scopes = USER_SCOPES.copy()
                client_id = str(payload.get("client_id") or "rgone-portal")
            elif role == "admin":
                if not auth_cfg["trust_rgone_admin"]:
                    raise ValueError("RgOne admin JWT mapping is disabled")
                scopes = ADMIN_SCOPES.copy()
                client_id = str(payload.get("client_id") or "rgone-admin")
            else:
                raise ValueError(f"Unsupported RgOne role: {role or 'empty'}")

            return TokenPayload(
                sub=sub,
                client_id=client_id,
                scopes=scopes,
                exp=int(payload.get("exp") or 0),
                iat=int(payload.get("iat") or 0),
                iss=iss,
                name=str(payload.get("name") or ""),
            )

        raise ValueError(f"Untrusted token issuer: {iss}")
    except Exception as e:
        logger.warning("Token verification failed: %s", e)
        raise ValueError(f"Invalid token: {e}") from e


def check_tool_permission(
    user: TokenPayload,
    tool_id: str,
    tool_risk_level: str = "L0",
    granted_tool_ids: Optional[List[str]] = None,
    tool_namespace_name: Optional[str] = None,
) -> bool:
    """检查用户是否有权调用指定工具

    - 若具有 hub:admin 角色，拥有全部权限
    - 若工具属于 L0 风险等级，全员默认授权可用
    - 若属于非 L0 风险等级，必须在用户的 granted_tool_ids 授权列表中（精确匹配，严禁模糊匹配）
    """
    if "hub:admin" in user.scopes:
        return True
    if "hub:tools:call" not in user.scopes:
        return False
    risk_str = getattr(tool_risk_level, "value", str(tool_risk_level)).upper()
    if risk_str == "L0":
        return True
    if not granted_tool_ids:
        return False

    allowed_set = set(granted_tool_ids)
    if tool_id in allowed_set:
        return True
    if tool_namespace_name and tool_namespace_name in allowed_set:
        return True
    return False
