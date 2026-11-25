"""个人业务凭据对称加密与解密管理模块

规范与安全要求：
1. 采用经过广泛验证的标准认证加密（AES-128-CBC + HMAC-SHA256 通过 Fernet 实现）；
2. 严禁自制加密算法，严禁明文凭据入库；
3. 密钥通过环境变量 HUB_CREDENTIAL_ENCRYPTION_KEY 注入；生产模式下缺少密钥强制拒绝启动或操作；
4. 无论何时，解密后的凭据字典仅在受保护的服务端内存中短期存在，绝不落库、绝不写入审计日志与模型提示词。
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_FERNET_INSTANCE: Optional[Fernet] = None


def reset_fernet_cache() -> None:
    """重置进程内缓存的 Fernet 实例（用于测试或密钥轮换）"""
    global _FERNET_INSTANCE
    _FERNET_INSTANCE = None


def get_fernet() -> Fernet:
    """获取或初始化全局 Fernet 加密实例"""
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is not None:
        return _FERNET_INSTANCE

    raw_key = os.getenv("HUB_CREDENTIAL_ENCRYPTION_KEY", "").strip()
    env = os.getenv("HUB_ENV", "development").lower()

    if raw_key:
        try:
            # 尝试直接作为 32 字节 Base64 Fernet key 加载
            _FERNET_INSTANCE = Fernet(raw_key.encode("utf-8"))
            return _FERNET_INSTANCE
        except Exception:
            # 若不是标准 Fernet key，使用 PBKDF2 派生出标准 32 字节 key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"hub-credentials-static-salt-v1",
                iterations=100_000,
            )
            derived = base64.urlsafe_b64encode(kdf.derive(raw_key.encode("utf-8")))
            _FERNET_INSTANCE = Fernet(derived)
            return _FERNET_INSTANCE

    if env == "production":
        raise RuntimeError(
            "生产环境安全阻断：未配置环境变量 HUB_CREDENTIAL_ENCRYPTION_KEY，拒绝使用不安全的临时密钥托管员工凭据！"
        )

    # 开发/测试模式：派生确定性测试密钥
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"hub-dev-test-salt-2026",
        iterations=10_000,
    )
    dev_key = base64.urlsafe_b64encode(kdf.derive(b"hub-dev-default-master-key-change-in-prod"))
    _FERNET_INSTANCE = Fernet(dev_key)
    logger.info("Using development deterministic Fernet encryption key.")
    return _FERNET_INSTANCE


def encrypt_credentials(credentials: Dict[str, Any]) -> str:
    """加密凭据字典为密文字符串"""
    if not credentials:
        return ""
    fernet = get_fernet()
    raw_json = json.dumps(credentials, ensure_ascii=False)
    cipher_bytes = fernet.encrypt(raw_json.encode("utf-8"))
    return cipher_bytes.decode("utf-8")


def decrypt_credentials(encrypted_text: str) -> Dict[str, Any]:
    """解密密文字符串为原始凭据字典"""
    if not encrypted_text:
        return {}
    fernet = get_fernet()
    plain_bytes = fernet.decrypt(encrypted_text.encode("utf-8"))
    return json.loads(plain_bytes.decode("utf-8"))


def generate_credential_summary(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """生成不包含任何敏感密码的非保密脱敏摘要（仅供前端展示绑定账号和字段配置状态）"""
    summary: Dict[str, Any] = {}
    for k, v in credentials.items():
        k_lower = str(k).lower()
        if any(secret_kw in k_lower for secret_kw in ["password", "secret", "token", "key", "credential"]):
            summary[f"has_{k}"] = bool(v)
        else:
            summary[k] = v
    return summary
