"""认证与授权模块

MVP 阶段使用 JWT（python-jose）进行 token 验签。
后续可接入企业 IdP（OAuth2 / OIDC）。
"""

from __future__ import annotations

import logging
from typing import List, Optional

import contextvars
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

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

# MVP 密钥（生产环境应从配置/密钥管理服务加载）
_JWT_SECRET = "hub-dev-secret-change-me"
_JWT_ALGORITHM = "HS256"


class TokenPayload(BaseModel):
    """JWT Token 解析后的载荷"""

    sub: str = Field(..., description="用户 ID")
    client_id: str = Field(default="", description="客户端应用 ID")
    scopes: List[str] = Field(default_factory=list, description="授权范围列表")
    exp: int = Field(default=2147483647, description="过期时间戳（Unix epoch）")


current_user_cv: contextvars.ContextVar[Optional[TokenPayload]] = contextvars.ContextVar(
    "current_user_cv", default=None
)


def get_current_user() -> Optional[TokenPayload]:
    """获取当前请求上下文中的用户身份，默认为 guest"""
    return current_user_cv.get()


def set_current_user(user: Optional[TokenPayload]) -> None:
    """设置当前请求上下文中的用户身份"""
    current_user_cv.set(user)


def create_access_token(
    user_id: str,
    client_id: str = "ide-client",
    scopes: Optional[List[str]] = None,
    expires_delta_days: int = 30,
) -> str:
    """为指定用户和客户端签发带身份的 JWT 访问令牌"""
    if scopes is None:
        scopes = USER_SCOPES.copy()

    now = datetime.now(timezone.utc)
    exp = int((now + timedelta(days=expires_delta_days)).timestamp())
    payload = {
        "sub": user_id,
        "client_id": client_id,
        "scopes": scopes,
        "exp": exp,
        "iat": int(now.timestamp()),
    }
    encoded = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)
    if isinstance(encoded, bytes):
        return encoded.decode("utf-8")
    return encoded


def verify_token(token: str) -> TokenPayload:
    """验证 JWT Token 并返回解析后的载荷

    Args:
        token: Bearer token 字符串（不含 'Bearer ' 前缀）

    Returns:
        TokenPayload 实例

    Raises:
        ValueError: token 无效或已过期
    """
    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALGORITHM],
        )
        return TokenPayload(
            sub=payload.get("sub", ""),
            client_id=payload.get("client_id", ""),
            scopes=payload.get("scopes", []),
            exp=payload.get("exp", 0),
        )
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
