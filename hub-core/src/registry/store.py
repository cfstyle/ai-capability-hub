"""Registry 存储层

使用 SQLite 持久化服务和工具注册信息。
基于 Python 内置 sqlite3，并通过 asyncio.to_thread 提供异步调用接口。
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.registry.models import (
    CredentialFieldType,
    CredentialFieldSchema,
    InvocationLogItem,
    PermissionRequest,
    PermissionRequestCreate,
    PermissionRequestReview,
    PermissionRequestStatus,
    PortalCapabilityCard,
    PortalCapabilityDetail,
    PortalOverview,
    PortalToolItem,
    PortalTrendItem,
    RegisteredService,
    RegisteredTool,
    ServiceCredentialSchema,
    ServiceRegistration,
    ServiceStatus,
    ToolRiskLevel,
    UserGrant,
    UserMcpDetail,
    UserServiceBinding,
    UserServiceBindingCreate,
    UserServiceBindingUpdate,
)

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _row_to_service(r: sqlite3.Row) -> RegisteredService:
    """将 SQLite 数据行映射为 RegisteredService 模型"""
    keys = set(r.keys())
    examples = []
    if "usage_examples" in keys and r["usage_examples"]:
        try:
            parsed = json.loads(r["usage_examples"])
            if isinstance(parsed, list):
                examples = [str(x) for x in parsed]
        except Exception:
            examples = []

    return RegisteredService(
        id=r["id"],
        name=r["name"],
        description=r["description"] or "",
        endpoint_url=r["endpoint_url"],
        version=r["version"] if "version" in keys and r["version"] else "0.0.0",
        owner=r["owner"] or "",
        status=ServiceStatus(r["status"]),
        category=r["category"] if "category" in keys and r["category"] else "通用",
        auth_mode=r["auth_mode"] if "auth_mode" in keys and r["auth_mode"] else "platform_sso",
        auth_label=r["auth_label"] if "auth_label" in keys and r["auth_label"] else "Hub 统一认证",
        auth_guide=r["auth_guide"]
        if "auth_guide" in keys and r["auth_guide"]
        else "调用具体业务能力时，由 Capability Hub 统一进行身份校验与权限换发",
        auth_entry_url=r["auth_entry_url"] if "auth_entry_url" in keys and r["auth_entry_url"] else "",
        usage_examples=examples,
        credential_schema=(
            ServiceCredentialSchema(**json.loads(r["credential_schema"]))
            if ("credential_schema" in keys and r["credential_schema"])
            else None
        ),
        trusted_credential_recipient=bool(r["trusted_credential_recipient"]) if "trusted_credential_recipient" in keys else False,
        trusted_credential_version=r["trusted_credential_version"] if "trusted_credential_version" in keys else None,
        trusted_credential_endpoint_url=r["trusted_credential_endpoint_url"] if "trusted_credential_endpoint_url" in keys else None,
        trusted_confirmed_by=r["trusted_confirmed_by"] if "trusted_confirmed_by" in keys else None,
        trusted_confirmed_at=(
            _parse_iso(r["trusted_confirmed_at"])
            if ("trusted_confirmed_at" in keys and r["trusted_confirmed_at"])
            else None
        ),
        downstream_status=(
            r["downstream_status"]
            if ("downstream_status" in keys and r["downstream_status"])
            else "available"
        ),
        downstream_error=r["downstream_error"] if "downstream_error" in keys else None,
        created_at=_parse_iso(r["created_at"]),
        updated_at=_parse_iso(r["updated_at"]),
    )


def _row_to_permission_request(
    r: sqlite3.Row,
    tool_map: Optional[Dict[str, str]] = None,
    service_name: str = "",
) -> PermissionRequest:
    keys = set(r.keys())
    tool_ids_raw = r["tool_ids"] or "[]"
    try:
        tool_ids = json.loads(tool_ids_raw) if isinstance(tool_ids_raw, str) else list(tool_ids_raw)
    except Exception:
        tool_ids = []

    tool_names = [tool_map.get(tid, tid) for tid in tool_ids] if tool_map else []
    has_cred = bool(r["has_credential_binding"]) if "has_credential_binding" in keys else False
    cred_summary = None
    if "credential_summary" in keys and r["credential_summary"]:
        try:
            cred_summary = json.loads(r["credential_summary"])
        except Exception:
            cred_summary = None

    return PermissionRequest(
        id=r["id"],
        user_id=r["user_id"],
        user_name=r["user_name"] or "",
        service_id=r["service_id"],
        service_name=service_name or r["service_id"],
        tool_ids=tool_ids,
        tool_names=tool_names,
        reason=r["reason"] or "",
        has_credential_binding=has_cred,
        credential_summary=cred_summary,
        status=PermissionRequestStatus(r["status"]),
        created_at=_parse_iso(r["created_at"]),
        reviewed_by=r["reviewed_by"],
        reviewed_at=_parse_iso(r["reviewed_at"]) if r["reviewed_at"] else None,
        comment=r["comment"],
    )


class RegistryStore:
    """服务与工具注册表存储层"""

    def __init__(self, db_path: str = "data/hub.db") -> None:
        self.db_path = db_path
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        path = Path(self.db_path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    async def init_db(self) -> None:
        """初始化 SQLite 数据库与表结构，平滑增量迁移字段 (ADR-009)"""
        def _init_sync():
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS services (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        endpoint_url TEXT NOT NULL,
                        version TEXT DEFAULT '0.0.0',
                        owner TEXT DEFAULT '',
                        status TEXT DEFAULT 'active',
                        category TEXT DEFAULT '通用',
                        auth_mode TEXT DEFAULT 'platform_sso',
                        auth_label TEXT DEFAULT 'Hub 统一认证',
                        auth_guide TEXT DEFAULT '调用具体业务能力时，由 Capability Hub 统一进行身份校验与权限换发',
                        auth_entry_url TEXT DEFAULT '',
                        usage_examples TEXT DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)
                # 动态探测现有 services 表列（处理已有旧数据库升级场景，零破坏原有数据）
                cur = conn.cursor()
                cur.execute("PRAGMA table_info(services);")
                columns = {col["name"] for col in cur.fetchall()}
                column_defs = [
                    ("category", "TEXT DEFAULT '通用'"),
                    ("auth_mode", "TEXT DEFAULT 'platform_sso'"),
                    ("auth_label", "TEXT DEFAULT 'Hub 统一认证'"),
                    ("auth_guide", "TEXT DEFAULT '调用具体业务能力时，由 Capability Hub 统一进行身份校验与权限换发'"),
                    ("auth_entry_url", "TEXT DEFAULT ''"),
                    ("usage_examples", "TEXT DEFAULT '[]'"),
                    ("credential_schema", "TEXT DEFAULT NULL"),
                    ("trusted_credential_recipient", "INTEGER DEFAULT 0"),
                    ("trusted_credential_version", "TEXT DEFAULT NULL"),
                    ("trusted_credential_endpoint_url", "TEXT DEFAULT NULL"),
                    ("trusted_confirmed_by", "TEXT DEFAULT NULL"),
                    ("trusted_confirmed_at", "TEXT DEFAULT NULL"),
                    ("downstream_status", "TEXT DEFAULT 'available'"),
                    ("downstream_error", "TEXT DEFAULT NULL"),
                ]
                for col_name, col_def in column_defs:
                    if col_name not in columns:
                        conn.execute(f"ALTER TABLE services ADD COLUMN {col_name} {col_def};")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tools (
                        id TEXT PRIMARY KEY,
                        service_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        input_schema TEXT DEFAULT '{}',
                        risk_level TEXT DEFAULT 'L0',
                        requires_confirmation INTEGER DEFAULT 0,
                        requires_credentials INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
                        UNIQUE(service_id, name)
                    );
                """)
                cur.execute("PRAGMA table_info(tools);")
                tool_cols = {col["name"] for col in cur.fetchall()}
                if "requires_credentials" not in tool_cols:
                    conn.execute("ALTER TABLE tools ADD COLUMN requires_credentials INTEGER DEFAULT 0;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS invocation_logs (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        client_id TEXT NOT NULL,
                        service_id TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        params_summary TEXT NOT NULL,
                        result_status TEXT NOT NULL,
                        duration_ms REAL NOT NULL,
                        trace_id TEXT DEFAULT ''
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON invocation_logs(timestamp);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_service ON invocation_logs(service_id);")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_grants (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        tool_id TEXT NOT NULL,
                        granted_by TEXT DEFAULT 'admin',
                        granted_at TEXT NOT NULL,
                        status TEXT DEFAULT 'active',
                        UNIQUE(user_id, tool_id)
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_grants_user ON user_grants(user_id);")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS permission_requests (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        user_name TEXT DEFAULT '',
                        service_id TEXT NOT NULL,
                        tool_ids TEXT NOT NULL,
                        reason TEXT DEFAULT '',
                        has_credential_binding INTEGER DEFAULT 0,
                        credential_summary TEXT DEFAULT '{}',
                        status TEXT DEFAULT 'pending',
                        created_at TEXT NOT NULL,
                        reviewed_by TEXT DEFAULT NULL,
                        reviewed_at TEXT DEFAULT NULL,
                        comment TEXT DEFAULT NULL
                    );
                """)
                cur.execute("PRAGMA table_info(permission_requests);")
                pr_cols = {col["name"] for col in cur.fetchall()}
                for pr_c, pr_def in [("has_credential_binding", "INTEGER DEFAULT 0"), ("credential_summary", "TEXT DEFAULT '{}'")]:
                    if pr_c not in pr_cols:
                        conn.execute(f"ALTER TABLE permission_requests ADD COLUMN {pr_c} {pr_def};")

                conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_req_user ON permission_requests(user_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_perm_req_status ON permission_requests(status);")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_service_bindings (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        service_id TEXT NOT NULL,
                        encrypted_credentials TEXT NOT NULL,
                        credential_summary TEXT NOT NULL,
                        credential_version INTEGER NOT NULL DEFAULT 1,
                        status TEXT NOT NULL DEFAULT 'active',
                        validation_status TEXT NOT NULL DEFAULT 'saved',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(user_id, service_id)
                    );
                """)
                cur.execute("PRAGMA table_info(user_service_bindings);")
                usb_cols = {col["name"] for col in cur.fetchall()}
                if "validation_status" not in usb_cols:
                    conn.execute("ALTER TABLE user_service_bindings ADD COLUMN validation_status TEXT NOT NULL DEFAULT 'saved';")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_usb_user_svc ON user_service_bindings(user_id, service_id);")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_revocations (
                        emp_no TEXT PRIMARY KEY,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        revoked_before INTEGER NOT NULL DEFAULT 0,
                        reason TEXT DEFAULT '',
                        updated_at TEXT NOT NULL
                    );
                """)
                conn.commit()

        await asyncio.to_thread(_init_sync)
        logger.info("Registry DB initialized at %s", self.db_path)

    async def register_service(
        self, registration: ServiceRegistration
    ) -> RegisteredService:
        """注册或更新服务信息（凭据接收方默认不受信任，版本或目标地址变更后自动失效需重新确认）"""
        now = _utc_now_iso()
        usage_ex_json = json.dumps(registration.usage_examples or [], ensure_ascii=False)
        cred_schema_json = (
            json.dumps(registration.credential_schema.model_dump(), ensure_ascii=False)
            if registration.credential_schema
            else None
        )
        new_version = (registration.version or "1.0.0").strip() or "1.0.0"

        def _sync_op() -> RegisteredService:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT created_at, status, version, endpoint_url, trusted_credential_recipient, trusted_credential_version, trusted_credential_endpoint_url, trusted_confirmed_by, trusted_confirmed_at FROM services WHERE id = ?",
                    (registration.service_id,),
                )
                row = cur.fetchone()
                if row:
                    # 仅当此前已确认可信且版本与目标地址均未变化时保留可信状态；任一变更立即失效
                    was_trusted = bool(row["trusted_credential_recipient"])
                    same_binding = (
                        was_trusted
                        and row["trusted_credential_version"] == new_version
                        and row["trusted_credential_endpoint_url"] == registration.endpoint_url
                    )
                    if same_binding:
                        trusted_val = 1
                        trusted_ver = row["trusted_credential_version"]
                        trusted_url = row["trusted_credential_endpoint_url"]
                        confirmed_by = row["trusted_confirmed_by"]
                        confirmed_at = row["trusted_confirmed_at"]
                    else:
                        trusted_val = 0
                        trusted_ver = None
                        trusted_url = None
                        confirmed_by = None
                        confirmed_at = None

                    cur.execute("""
                        UPDATE services 
                        SET name = ?, description = ?, endpoint_url = ?, version = ?, owner = ?, 
                            category = ?, auth_mode = ?, auth_label = ?, auth_guide = ?, auth_entry_url = ?, usage_examples = ?,
                            credential_schema = ?, trusted_credential_recipient = ?,
                            trusted_credential_version = ?, trusted_credential_endpoint_url = ?,
                            trusted_confirmed_by = ?, trusted_confirmed_at = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        registration.name,
                        registration.description,
                        registration.endpoint_url,
                        new_version,
                        registration.owner,
                        registration.category,
                        registration.auth_mode,
                        registration.auth_label,
                        registration.auth_guide,
                        registration.auth_entry_url,
                        usage_ex_json,
                        cred_schema_json,
                        trusted_val,
                        trusted_ver,
                        trusted_url,
                        confirmed_by,
                        confirmed_at,
                        now,
                        registration.service_id,
                    ))
                else:
                    created_at = now
                    status = ServiceStatus.ACTIVE.value
                    # 新增服务默认不受信任，必须由管理员独立确认
                    cur.execute("""
                        INSERT INTO services (id, name, description, endpoint_url, version, owner, status, category, auth_mode, auth_label, auth_guide, auth_entry_url, usage_examples, credential_schema, trusted_credential_recipient, trusted_credential_version, trusted_credential_endpoint_url, trusted_confirmed_by, trusted_confirmed_at, downstream_status, downstream_error, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, NULL, NULL, 'available', NULL, ?, ?)
                    """, (
                        registration.service_id,
                        registration.name,
                        registration.description,
                        registration.endpoint_url,
                        new_version,
                        registration.owner,
                        status,
                        registration.category,
                        registration.auth_mode,
                        registration.auth_label,
                        registration.auth_guide,
                        registration.auth_entry_url,
                        usage_ex_json,
                        cred_schema_json,
                        created_at,
                        now,
                    ))
                conn.commit()

                cur.execute("SELECT * FROM services WHERE id = ?", (registration.service_id,))
                return _row_to_service(cur.fetchone())

        return await asyncio.to_thread(_sync_op)

    async def confirm_credential_trust(
        self, service_id: str, trusted: bool, confirmed_by: str = "admin"
    ) -> Optional[RegisteredService]:
        """管理员独立确认/撤销服务的个人凭据接收方信任状态，并绑定当前插件版本与目标地址"""
        now = _utc_now_iso()

        def _sync_op() -> Optional[RegisteredService]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM services WHERE id = ?", (service_id,))
                row = cur.fetchone()
                if not row:
                    return None
                if trusted:
                    cur.execute("""
                        UPDATE services
                        SET trusted_credential_recipient = 1,
                            trusted_credential_version = ?,
                            trusted_credential_endpoint_url = ?,
                            trusted_confirmed_by = ?,
                            trusted_confirmed_at = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (row["version"], row["endpoint_url"], confirmed_by, now, now, service_id))
                else:
                    cur.execute("""
                        UPDATE services
                        SET trusted_credential_recipient = 0,
                            trusted_credential_version = NULL,
                            trusted_credential_endpoint_url = NULL,
                            trusted_confirmed_by = NULL,
                            trusted_confirmed_at = NULL,
                            updated_at = ?
                        WHERE id = ?
                    """, (now, service_id))
                conn.commit()
                cur.execute("SELECT * FROM services WHERE id = ?", (service_id,))
                return _row_to_service(cur.fetchone())

        return await asyncio.to_thread(_sync_op)

    async def update_downstream_status(
        self, service_id: str, downstream_status: str, downstream_error: Optional[str] = None
    ) -> None:
        """更新下游服务可达状态（available / unavailable）"""
        now = _utc_now_iso()

        def _sync_op() -> None:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE services
                    SET downstream_status = ?, downstream_error = ?, updated_at = ?
                    WHERE id = ?
                """, (downstream_status, downstream_error, now, service_id))
                conn.commit()

        await asyncio.to_thread(_sync_op)

    async def get_service(self, service_id: str) -> Optional[RegisteredService]:
        """按 service_id 查询服务详情"""
        def _sync_op() -> Optional[RegisteredService]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM services WHERE id = ?", (service_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return _row_to_service(row)

        return await asyncio.to_thread(_sync_op)

    async def list_services(
        self, status: Optional[ServiceStatus] = None
    ) -> List[RegisteredService]:
        """列出已注册的服务，可按状态筛选"""
        def _sync_op() -> List[RegisteredService]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                if status:
                    cur.execute("SELECT * FROM services WHERE status = ? ORDER BY created_at ASC", (status.value,))
                else:
                    cur.execute("SELECT * FROM services ORDER BY created_at ASC")
                rows = cur.fetchall()
                return [_row_to_service(r) for r in rows]

        return await asyncio.to_thread(_sync_op)

    async def update_service_status(
        self, service_id: str, status: ServiceStatus
    ) -> Optional[RegisteredService]:
        """更新服务状态（如 active, inactive, degraded）"""
        now = _utc_now_iso()

        def _sync_op() -> Optional[RegisteredService]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE services SET status = ?, updated_at = ? WHERE id = ?",
                    (status.value, now, service_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return None
            return True

        res = await asyncio.to_thread(_sync_op)
        if not res:
            return None
        return await self.get_service(service_id)

    async def save_tools(
        self,
        service_id: str,
        tools: List[RegisteredTool],
        preserve_policies: bool = True,
    ) -> None:
        """安全提交服务的工具快照（单事务原子切换，保留已有策略）"""
        now = _utc_now_iso()

        def _sync_op():
            with self._get_connection() as conn:
                cur = conn.cursor()
                # 1. 查询当前已有的旧工具列表，建立快照映射
                cur.execute("SELECT * FROM tools WHERE service_id = ?", (service_id,))
                old_rows = cur.fetchall()
                old_tools_map = {r["name"]: r for r in old_rows}

                # 2. 准备新工具快照（比对新旧快照，保留管理员已设定的风险级别与确认策略）
                prepared_tools = []
                for t in tools:
                    tool_id = t.id or f"{service_id}__{t.name}"
                    created_at = t.created_at.isoformat() if t.created_at else now
                    schema_json = json.dumps(t.input_schema or {})

                    final_risk = t.risk_level.value if isinstance(t.risk_level, ToolRiskLevel) else t.risk_level
                    final_req_confirm = 1 if t.requires_confirmation else 0
                    explicit_creds = getattr(t, "requires_credentials_explicit", None)
                    final_req_creds = (
                        1
                        if (explicit_creds if explicit_creds is not None else getattr(t, "requires_credentials", False))
                        else 0
                    )

                    if preserve_policies and t.name in old_tools_map:
                        old_r = old_tools_map[t.name]
                        # 核心防退化保护：保留管理员此前调整过的人工策略、凭据声明（若未显式覆盖）与创建时间
                        final_risk = old_r["risk_level"]
                        final_req_confirm = old_r["requires_confirmation"]
                        created_at = old_r["created_at"]
                        if explicit_creds is None and "requires_credentials" in old_r.keys():
                            final_req_creds = old_r["requires_credentials"]

                    prepared_tools.append((
                        tool_id,
                        service_id,
                        t.name,
                        t.description or "",
                        schema_json,
                        final_risk,
                        final_req_confirm,
                        final_req_creds,
                        created_at,
                    ))

                # 3. 单事务原子替换
                cur.execute("DELETE FROM tools WHERE service_id = ?", (service_id,))
                cur.executemany("""
                    INSERT INTO tools (id, service_id, name, description, input_schema, risk_level, requires_confirmation, requires_credentials, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, prepared_tools)
                conn.commit()

        await asyncio.to_thread(_sync_op)

    async def list_tools(
        self, service_id: Optional[str] = None
    ) -> List[RegisteredTool]:
        """查询已注册工具，可按 service_id 筛选"""
        def _sync_op() -> List[RegisteredTool]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                if service_id:
                    cur.execute("SELECT * FROM tools WHERE service_id = ? ORDER BY name ASC", (service_id,))
                else:
                    cur.execute("SELECT * FROM tools ORDER BY service_id ASC, name ASC")
                rows = cur.fetchall()
                results = []
                for r in rows:
                    schema = {}
                    try:
                        schema = json.loads(r["input_schema"])
                    except Exception:
                        pass
                    results.append(
                        RegisteredTool(
                            id=r["id"],
                            service_id=r["service_id"],
                            name=r["name"],
                            description=r["description"],
                            input_schema=schema,
                            risk_level=ToolRiskLevel(r["risk_level"]),
                            requires_confirmation=bool(r["requires_confirmation"]),
                            requires_credentials=bool(r["requires_credentials"]) if "requires_credentials" in r.keys() else False,
                            created_at=_parse_iso(r["created_at"]),
                        )
                    )
                return results

        return await asyncio.to_thread(_sync_op)

    async def get_tool_by_namespace_name(
        self, namespace_name: str
    ) -> Optional[RegisteredTool]:
        """按命名空间名称查找工具 ({service_id}__{tool_name} 或 {service_id}_{tool_name} 或 id)"""
        def _sync_op() -> Optional[RegisteredTool]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                # 1. 直接按 id 匹配
                cur.execute("SELECT * FROM tools WHERE id = ?", (namespace_name,))
                r = cur.fetchone()
                if not r:
                    # 2. 直接按 name 匹配
                    cur.execute("SELECT * FROM tools WHERE name = ?", (namespace_name,))
                    r = cur.fetchone()
                if not r and "__" in namespace_name:
                    sid, tname = namespace_name.split("__", 1)
                    cur.execute("SELECT * FROM tools WHERE service_id = ? AND name = ?", (sid, tname))
                    r = cur.fetchone()
                if not r and "_" in namespace_name:
                    sid, tname = namespace_name.split("_", 1)
                    cur.execute("SELECT * FROM tools WHERE service_id = ? AND name = ?", (sid, tname))
                    r = cur.fetchone()
                if not r:
                    return None
                schema = {}
                try:
                    schema = json.loads(r["input_schema"])
                except Exception:
                    pass
                return RegisteredTool(
                    id=r["id"],
                    service_id=r["service_id"],
                    name=r["name"],
                    description=r["description"],
                    input_schema=schema,
                    risk_level=ToolRiskLevel(r["risk_level"]),
                    requires_confirmation=bool(r["requires_confirmation"]),
                    requires_credentials=bool(r["requires_credentials"]) if "requires_credentials" in r.keys() else False,
                    created_at=_parse_iso(r["created_at"]),
                )

        return await asyncio.to_thread(_sync_op)

    async def update_service_metadata(
        self,
        service_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        owner: Optional[str] = None,
        category: Optional[str] = None,
        auth_mode: Optional[str] = None,
        auth_label: Optional[str] = None,
        auth_guide: Optional[str] = None,
        auth_entry_url: Optional[str] = None,
        usage_examples: Optional[List[str]] = None,
    ) -> Optional[RegisteredService]:
        """更新服务名称、描述、负责人元数据及公开门户展示字段"""
        now = _utc_now_iso()

        def _sync_op() -> bool:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM services WHERE id = ?", (service_id,))
                row = cur.fetchone()
                if not row:
                    return False
                keys = set(row.keys())
                new_name = name if name is not None else row["name"]
                new_desc = description if description is not None else row["description"]
                new_owner = owner if owner is not None else row["owner"]
                new_category = category if category is not None else (row["category"] if "category" in keys else "通用")
                new_auth_mode = auth_mode if auth_mode is not None else (row["auth_mode"] if "auth_mode" in keys else "platform_sso")
                new_auth_label = auth_label if auth_label is not None else (row["auth_label"] if "auth_label" in keys else "Hub 统一认证")
                new_auth_guide = auth_guide if auth_guide is not None else (row["auth_guide"] if "auth_guide" in keys else "调用具体业务能力时，由 Capability Hub 统一进行身份校验与权限换发")
                new_auth_entry_url = auth_entry_url if auth_entry_url is not None else (row["auth_entry_url"] if "auth_entry_url" in keys else "")
                new_usage_examples = json.dumps(usage_examples, ensure_ascii=False) if usage_examples is not None else (row["usage_examples"] if "usage_examples" in keys else "[]")

                cur.execute(
                    """
                    UPDATE services 
                    SET name = ?, description = ?, owner = ?, category = ?, auth_mode = ?, 
                        auth_label = ?, auth_guide = ?, auth_entry_url = ?, usage_examples = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        new_name,
                        new_desc,
                        new_owner,
                        new_category,
                        new_auth_mode,
                        new_auth_label,
                        new_auth_guide,
                        new_auth_entry_url,
                        new_usage_examples,
                        now,
                        service_id,
                    ),
                )
                conn.commit()
                return True

        found = await asyncio.to_thread(_sync_op)
        if not found:
            return None
        return await self.get_service(service_id)

    async def update_tool_policy(
        self,
        tool_id: str,
        risk_level: ToolRiskLevel,
        requires_confirmation: bool,
    ) -> Optional[RegisteredTool]:
        """更新工具风险等级与人工确认策略"""
        def _sync_op() -> Optional[str]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM tools WHERE id = ?", (tool_id,))
                row = cur.fetchone()
                if not row and "__" in tool_id:
                    s_id, t_name = tool_id.split("__", 1)
                    cur.execute("SELECT id FROM tools WHERE service_id = ? AND name = ?", (s_id, t_name))
                    row = cur.fetchone()
                if not row:
                    cur.execute("SELECT id FROM tools WHERE name = ?", (tool_id,))
                    row = cur.fetchone()
                if not row:
                    return None
                actual_id = row["id"]
                val = risk_level.value if isinstance(risk_level, ToolRiskLevel) else risk_level
                cur.execute(
                    "UPDATE tools SET risk_level = ?, requires_confirmation = ? WHERE id = ?",
                    (val, 1 if requires_confirmation else 0, actual_id),
                )
                conn.commit()
                return actual_id

        actual_id = await asyncio.to_thread(_sync_op)
        if not actual_id:
            return None
        tools = await self.list_tools()
        for t in tools:
            if t.id == actual_id:
                return t
        return None

    async def save_invocation_log(self, entry: Dict[str, Any]) -> None:
        """保存工具调用审计日志"""
        log_id = entry.get("id") or str(uuid.uuid4())
        ts = entry.get("timestamp") or _utc_now_iso()
        params_str = json.dumps(entry.get("params_summary") or {}, ensure_ascii=False)

        def _sync_op():
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO invocation_logs (id, timestamp, user_id, client_id, service_id, tool_name, params_summary, result_status, duration_ms, trace_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_id,
                    ts,
                    entry.get("user_id", "default-agent"),
                    entry.get("client_id", "mcp-client"),
                    entry.get("service_id", "hub"),
                    entry.get("tool_name", "unknown"),
                    params_str,
                    entry.get("result_status", "unknown"),
                    float(entry.get("duration_ms", 0.0)),
                    entry.get("trace_id", "") or "",
                ))
                conn.commit()

        await asyncio.to_thread(_sync_op)

    async def list_invocation_logs(
        self,
        service_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InvocationLogItem], int]:
        """分页与条件查询工具调用审计日志"""
        def _sync_op() -> Tuple[List[InvocationLogItem], int]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                where_clauses = []
                params: List[Any] = []
                if service_id:
                    where_clauses.append("service_id = ?")
                    params.append(service_id)
                if tool_name:
                    where_clauses.append("tool_name LIKE ?")
                    params.append(f"%{tool_name}%")
                if status:
                    where_clauses.append("result_status LIKE ?")
                    params.append(f"%{status}%")

                where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

                cur.execute(f"SELECT COUNT(*) as cnt FROM invocation_logs{where_sql}", tuple(params))
                total_cnt = cur.fetchone()["cnt"]

                query_sql = f"SELECT * FROM invocation_logs{where_sql} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                cur.execute(query_sql, tuple(params + [limit, offset]))
                rows = cur.fetchall()

                items = []
                for r in rows:
                    params_summary = {}
                    try:
                        params_summary = json.loads(r["params_summary"])
                    except Exception:
                        pass
                    items.append(
                        InvocationLogItem(
                            id=r["id"],
                            timestamp=r["timestamp"],
                            user_id=r["user_id"],
                            client_id=r["client_id"],
                            service_id=r["service_id"],
                            tool_name=r["tool_name"],
                            params_summary=params_summary,
                            result_status=r["result_status"],
                            duration_ms=r["duration_ms"],
                            trace_id=r["trace_id"] or "",
                        )
                    )
                return items, total_cnt

        return await asyncio.to_thread(_sync_op)

    async def get_invocation_summary(self) -> Dict[str, int]:
        """汇总全量调用统计（总次数、成功次数、失败/拦截次数）"""
        def _sync_op() -> Dict[str, int]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT
                        COUNT(*) AS total_calls,
                        COALESCE(SUM(CASE WHEN LOWER(result_status) = 'success' THEN 1 ELSE 0 END), 0) AS success_calls
                    FROM invocation_logs
                """)
                row = cur.fetchone()
                total = int(row["total_calls"] or 0)
                success = int(row["success_calls"] or 0)
                return {
                    "calls_total": total,
                    "calls_success": success,
                    "calls_failed": max(0, total - success),
                }

        return await asyncio.to_thread(_sync_op)

    async def get_portal_overview(self) -> PortalOverview:
        """获取面向门户的真实运行概览与7天调用趋势"""
        from datetime import timedelta

        def _sync_op() -> PortalOverview:
            with self._get_connection() as conn:
                cur = conn.cursor()
                # 1. 已发布可用服务总数与全量服务数
                cur.execute("SELECT COUNT(*) as cnt FROM services WHERE status = 'active'")
                active_svcs = cur.fetchone()["cnt"]

                cur.execute("SELECT COUNT(*) as cnt FROM services")
                total_svcs = cur.fetchone()["cnt"]

                # 2. 已发布可用服务的可用工具数
                cur.execute("""
                    SELECT COUNT(*) as cnt FROM tools t
                    JOIN services s ON t.service_id = s.id
                    WHERE s.status = 'active'
                """)
                tools_cnt = cur.fetchone()["cnt"]

                # 3. 真实总调用次数
                cur.execute("SELECT COUNT(*) as cnt FROM invocation_logs")
                total_calls = cur.fetchone()["cnt"]

                # 4. 健康率
                health_rate = round((active_svcs / total_svcs * 100), 1) if total_svcs > 0 else 100.0

                # 5. 近 7 日每日调用趋势 (真实数据聚合，无数据展示0)
                now_utc = datetime.now(timezone.utc)
                days = [(now_utc - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
                start_day = days[0]

                cur.execute("""
                    SELECT substr(timestamp, 1, 10) as log_day,
                           COUNT(*) as day_total,
                           COALESCE(SUM(CASE WHEN LOWER(result_status) = 'success' THEN 1 ELSE 0 END), 0) as day_succ
                    FROM invocation_logs
                    WHERE substr(timestamp, 1, 10) >= ?
                    GROUP BY log_day
                """, (start_day,))
                trend_map = {row["log_day"]: (row["day_total"], row["day_succ"]) for row in cur.fetchall()}

                daily_trends = []
                for d in days:
                    tot, succ = trend_map.get(d, (0, 0))
                    daily_trends.append(PortalTrendItem(
                        date=d,
                        calls=tot,
                        success_calls=succ,
                    ))

                return PortalOverview(
                    services_count=active_svcs,
                    tools_count=tools_cnt,
                    total_calls=total_calls,
                    active_services_count=active_svcs,
                    health_rate=health_rate,
                    daily_trends=daily_trends,
                )

        return await asyncio.to_thread(_sync_op)

    async def list_portal_capabilities(
        self,
        q: Optional[str] = None,
        category: Optional[str] = None,
        sort_by: str = "popular",
    ) -> List[PortalCapabilityCard]:
        """获取门户公开能力卡片列表（严格脱敏、仅 active、真实调用量驱动）"""
        from datetime import timedelta

        def _sync_op() -> List[PortalCapabilityCard]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                now_utc = datetime.now(timezone.utc)
                seven_days_ago = (now_utc - timedelta(days=7)).isoformat()

                # 1. 查询所有 active 服务（绝不泄露草稿、未发布或停用服务）
                cur.execute("SELECT * FROM services WHERE status = 'active' ORDER BY created_at ASC")
                service_rows = cur.fetchall()

                # 2. 查询各服务可用工具数量
                cur.execute("SELECT service_id, COUNT(*) as cnt FROM tools GROUP BY service_id")
                tool_counts = {r["service_id"]: r["cnt"] for r in cur.fetchall()}

                # 3. 查询各服务工具详情，用于关键字模糊搜索
                cur.execute("SELECT service_id, name, description FROM tools")
                service_tools: Dict[str, List[Tuple[str, str]]] = {}
                for r in cur.fetchall():
                    service_tools.setdefault(r["service_id"], []).append((r["name"], r["description"] or ""))

                # 4. 查询各服务的真实调用统计
                cur.execute("""
                    SELECT service_id,
                           COUNT(*) as total_calls,
                           SUM(CASE WHEN timestamp >= ? THEN 1 ELSE 0 END) as recent_calls,
                           MAX(timestamp) as last_active
                    FROM invocation_logs
                    GROUP BY service_id
                """, (seven_days_ago,))
                stats_map = {
                    r["service_id"]: {
                        "total_calls": r["total_calls"],
                        "recent_calls": r["recent_calls"] or 0,
                        "last_active": r["last_active"],
                    }
                    for r in cur.fetchall()
                }

                cards: List[PortalCapabilityCard] = []
                keyword = (q or "").strip().lower()

                for row in service_rows:
                    svc = _row_to_service(row)
                    # 分类筛选
                    if category and category != "全部" and svc.category != category:
                        continue

                    # 关键词匹配（服务名、业务描述、分类、工具名、工具描述）
                    if keyword:
                        name_match = keyword in svc.name.lower()
                        desc_match = keyword in (svc.description or "").lower()
                        cat_match = keyword in (svc.category or "").lower()
                        tools_match = any(
                            keyword in t_name.lower() or keyword in t_desc.lower()
                            for t_name, t_desc in service_tools.get(svc.id, [])
                        )
                        if not (name_match or desc_match or cat_match or tools_match):
                            continue

                    stat = stats_map.get(svc.id, {"total_calls": 0, "recent_calls": 0, "last_active": None})

                    cards.append(PortalCapabilityCard(
                        id=svc.id,
                        name=svc.name,
                        description=svc.description,
                        category=svc.category,
                        tools_count=tool_counts.get(svc.id, 0),
                        status=svc.status,
                        auth_mode=svc.auth_mode,
                        auth_label=svc.auth_label,
                        auth_guide=svc.auth_guide,
                        auth_entry_url=svc.auth_entry_url,
                        call_count=stat["total_calls"],
                        recent_calls_7d=stat["recent_calls"],
                        last_active_at=stat["last_active"],
                        created_at=svc.created_at,
                    ))

                # 排序逻辑
                if sort_by == "popular":
                    cards.sort(key=lambda c: (c.call_count, c.created_at), reverse=True)
                elif sort_by == "recent_active":
                    cards.sort(key=lambda c: (c.last_active_at or c.created_at.isoformat()), reverse=True)
                elif sort_by == "newest":
                    cards.sort(key=lambda c: c.created_at, reverse=True)
                elif sort_by == "name":
                    cards.sort(key=lambda c: c.name)

                return cards

        return await asyncio.to_thread(_sync_op)

    async def get_portal_capability_detail(
        self,
        service_id: str,
        public_gateway_url: str,
    ) -> Optional[PortalCapabilityDetail]:
        """获取单个能力公开详情（严格脱敏、仅 active）"""
        from datetime import timedelta

        def _sync_op() -> Optional[PortalCapabilityDetail]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM services WHERE id = ?", (service_id,))
                row = cur.fetchone()
                if not row:
                    return None
                svc = _row_to_service(row)
                if svc.status != ServiceStatus.ACTIVE:
                    return None

                # 查询该服务的已注册工具
                cur.execute("SELECT * FROM tools WHERE service_id = ? ORDER BY name ASC", (service_id,))
                tool_rows = cur.fetchall()
                tools: List[PortalToolItem] = []
                for tr in tool_rows:
                    schema = {}
                    try:
                        schema = json.loads(tr["input_schema"])
                    except Exception:
                        pass
                    tools.append(PortalToolItem(
                        id=tr["id"],
                        name=tr["name"],
                        namespace_name=f"{service_id}__{tr['name']}",
                        description=tr["description"] or "",
                        risk_level=ToolRiskLevel(tr["risk_level"]),
                        requires_confirmation=bool(tr["requires_confirmation"]),
                        requires_credentials=bool(tr["requires_credentials"]) if "requires_credentials" in tr.keys() else False,
                        input_schema=schema,
                    ))

                # 真实调用统计与 7 日趋势
                now_utc = datetime.now(timezone.utc)
                seven_days_ago = (now_utc - timedelta(days=7)).isoformat()
                cur.execute("""
                    SELECT COUNT(*) as total_calls,
                           SUM(CASE WHEN timestamp >= ? THEN 1 ELSE 0 END) as recent_calls,
                           MAX(timestamp) as last_active
                    FROM invocation_logs
                    WHERE service_id = ?
                """, (seven_days_ago, service_id))
                stat_row = cur.fetchone()
                total_calls = stat_row["total_calls"] if stat_row else 0
                recent_calls = (stat_row["recent_calls"] or 0) if stat_row else 0
                last_active = stat_row["last_active"] if stat_row else None

                days = [(now_utc - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
                start_day = days[0]
                cur.execute("""
                    SELECT substr(timestamp, 1, 10) as log_day,
                           COUNT(*) as day_total,
                           COALESCE(SUM(CASE WHEN LOWER(result_status) = 'success' THEN 1 ELSE 0 END), 0) as day_succ
                    FROM invocation_logs
                    WHERE service_id = ? AND substr(timestamp, 1, 10) >= ?
                    GROUP BY log_day
                """, (service_id, start_day))
                trend_map = {r["log_day"]: (r["day_total"], r["day_succ"]) for r in cur.fetchall()}

                daily_trends = []
                for d in days:
                    tot, succ = trend_map.get(d, (0, 0))
                    daily_trends.append(PortalTrendItem(
                        date=d,
                        calls=tot,
                        success_calls=succ,
                    ))

                # 适用场景/示例问法：若数据库中为空，则自动基于已有工具生成友好提示
                examples = svc.usage_examples
                if not examples and tools:
                    examples = [
                        f"帮我查询 {svc.name} 的相关信息",
                        f"使用 {tools[0].name} 分析业务数据",
                    ]

                return PortalCapabilityDetail(
                    id=svc.id,
                    name=svc.name,
                    description=svc.description,
                    category=svc.category,
                    version=svc.version,
                    status=svc.status,
                    created_at=svc.created_at,
                    auth_mode=svc.auth_mode,
                    auth_label=svc.auth_label,
                    auth_guide=svc.auth_guide,
                    auth_entry_url=svc.auth_entry_url,
                    credential_schema=svc.credential_schema,
                    usage_examples=examples,
                    gateway_url=public_gateway_url,
                    protocol="Streamable HTTP",
                    tools=tools,
                    total_calls=total_calls,
                    recent_calls_7d=recent_calls,
                    daily_trends=daily_trends,
                    last_active_at=last_active,
                )

        return await asyncio.to_thread(_sync_op)

    async def grant_tools(
        self, user_id: str, tool_ids: List[str], granted_by: str = "admin"
    ) -> List[UserGrant]:
        """批量为指定用户授予工具权限"""
        now = _utc_now_iso()

        def _sync_op() -> List[UserGrant]:
            results: List[UserGrant] = []
            with self._get_connection() as conn:
                cur = conn.cursor()
                for tool_id in tool_ids:
                    grant_id = f"grant_{uuid.uuid4().hex[:12]}"
                    cur.execute("""
                        INSERT INTO user_grants (id, user_id, tool_id, granted_by, granted_at, status)
                        VALUES (?, ?, ?, ?, ?, 'active')
                        ON CONFLICT(user_id, tool_id) DO UPDATE SET
                            granted_by = excluded.granted_by,
                            granted_at = excluded.granted_at,
                            status = 'active'
                    """, (grant_id, user_id, tool_id, granted_by, now))
                    results.append(UserGrant(
                        id=grant_id,
                        user_id=user_id,
                        tool_id=tool_id,
                        granted_by=granted_by,
                        granted_at=_parse_iso(now),
                        status="active",
                    ))
                conn.commit()
            return results

        return await asyncio.to_thread(_sync_op)

    async def revoke_tool_grant(self, user_id: str, tool_id: str) -> bool:
        """撤销指定用户的工具权限"""
        def _sync_op() -> bool:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE user_grants SET status = 'revoked' WHERE user_id = ? AND tool_id = ?",
                    (user_id, tool_id),
                )
                conn.commit()
                return cur.rowcount > 0

        return await asyncio.to_thread(_sync_op)

    async def get_user_granted_tool_ids(self, user_id: str) -> List[str]:
        """查询用户当前有效授权的所有 tool_id 列表"""
        def _sync_op() -> List[str]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT tool_id FROM user_grants WHERE user_id = ? AND status = 'active'",
                    (user_id,),
                )
                return [row["tool_id"] for row in cur.fetchall()]

        return await asyncio.to_thread(_sync_op)

    async def create_permission_request(
        self, req: PermissionRequestCreate
    ) -> PermissionRequest:
        """提交新的权限申请单，可同步关联或保存个人业务凭据"""
        req_id = f"req_{uuid.uuid4().hex[:12]}"
        now = _utc_now_iso()
        tool_ids_json = json.dumps(req.tool_ids, ensure_ascii=False)

        # 若申请中附带了凭据，先安全保存加密绑定
        has_cred = False
        summary_dict = {}
        if req.credentials:
            binding = await self.save_user_binding(req.user_id, req.service_id, req.credentials)
            has_cred = True
            summary_dict = binding.credential_summary
        else:
            # 检查是否此前已有针对该服务的绑定
            existing_binding = await self.get_user_binding(req.user_id, req.service_id)
            if existing_binding and existing_binding.status == "active":
                has_cred = True
                summary_dict = existing_binding.credential_summary

        summary_json = json.dumps(summary_dict, ensure_ascii=False) if summary_dict else "{}"

        def _sync_op() -> PermissionRequest:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO permission_requests 
                    (id, user_id, user_name, service_id, tool_ids, reason, has_credential_binding, credential_summary, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """, (
                    req_id,
                    req.user_id,
                    req.user_name,
                    req.service_id,
                    tool_ids_json,
                    req.reason,
                    1 if has_cred else 0,
                    summary_json,
                    now,
                ))
                conn.commit()

                # 填充 service_name 与 tool_names
                cur.execute("SELECT name FROM services WHERE id = ?", (req.service_id,))
                svc_row = cur.fetchone()
                svc_name = svc_row["name"] if svc_row else req.service_id

                tool_map = {}
                if req.tool_ids:
                    placeholders = ",".join(["?"] * len(req.tool_ids))
                    cur.execute(f"SELECT id, name FROM tools WHERE id IN ({placeholders})", req.tool_ids)
                    tool_map = {r["id"]: r["name"] for r in cur.fetchall()}

                return PermissionRequest(
                    id=req_id,
                    user_id=req.user_id,
                    user_name=req.user_name,
                    service_id=req.service_id,
                    service_name=svc_name,
                    tool_ids=req.tool_ids,
                    tool_names=[tool_map.get(tid, tid) for tid in req.tool_ids],
                    reason=req.reason,
                    has_credential_binding=has_cred,
                    credential_summary=summary_dict if summary_dict else None,
                    status=PermissionRequestStatus.PENDING,
                    created_at=_parse_iso(now),
                )

        return await asyncio.to_thread(_sync_op)

    async def list_permission_requests(
        self, user_id: Optional[str] = None, status: Optional[PermissionRequestStatus] = None
    ) -> List[PermissionRequest]:
        """查询权限申请单列表（支持按申请人或状态筛选）"""
        def _sync_op() -> List[PermissionRequest]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                query = "SELECT * FROM permission_requests WHERE 1=1"
                params: List[Any] = []
                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)
                if status:
                    query += " AND status = ?"
                    params.append(status.value if isinstance(status, PermissionRequestStatus) else str(status))
                query += " ORDER BY created_at DESC"
                cur.execute(query, params)
                rows = cur.fetchall()

                # 批量获取服务名映射与工具名映射
                cur.execute("SELECT id, name FROM services")
                svc_map = {r["id"]: r["name"] for r in cur.fetchall()}
                cur.execute("SELECT id, name FROM tools")
                tool_map = {r["id"]: r["name"] for r in cur.fetchall()}

                res = []
                for r in rows:
                    res.append(_row_to_permission_request(
                        r,
                        tool_map=tool_map,
                        service_name=svc_map.get(r["service_id"], r["service_id"])
                    ))
                return res

        return await asyncio.to_thread(_sync_op)

    async def review_permission_request(
        self, request_id: str, review: PermissionRequestReview
    ) -> Optional[PermissionRequest]:
        """审批权限申请单：仅待审状态可审批，事务内原子更新状态并写入 user_grants"""
        now = _utc_now_iso()

        def _sync_op() -> Optional[PermissionRequest]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM permission_requests WHERE id = ?", (request_id,))
                row = cur.fetchone()
                if not row:
                    return None

                current_status = row["status"]
                if current_status != PermissionRequestStatus.PENDING.value:
                    raise ValueError(
                        f"Permission request '{request_id}' has already been reviewed (current status: '{current_status}')"
                    )

                status_val = review.status.value if isinstance(review.status, PermissionRequestStatus) else str(review.status)
                cur.execute("""
                    UPDATE permission_requests
                    SET status = ?, reviewed_by = ?, reviewed_at = ?, comment = ?
                    WHERE id = ? AND status = 'pending'
                """, (status_val, review.reviewer, now, review.comment, request_id))
                if cur.rowcount == 0:
                    raise ValueError(f"Concurrent review conflict: request '{request_id}' status changed concurrently.")

                # 若审核通过，同一事务内自动写入 user_grants 授权
                if status_val == PermissionRequestStatus.APPROVED.value:
                    user_id = row["user_id"]
                    try:
                        tool_ids = json.loads(row["tool_ids"])
                    except Exception:
                        tool_ids = []
                    for tool_id in tool_ids:
                        grant_id = f"grant_{uuid.uuid4().hex[:12]}"
                        cur.execute("""
                            INSERT INTO user_grants (id, user_id, tool_id, granted_by, granted_at, status)
                            VALUES (?, ?, ?, ?, ?, 'active')
                            ON CONFLICT(user_id, tool_id) DO UPDATE SET
                                granted_by = excluded.granted_by,
                                granted_at = excluded.granted_at,
                                status = 'active'
                        """, (grant_id, user_id, tool_id, review.reviewer, now))

                conn.commit()

                # 返回更新后的记录
                cur.execute("SELECT * FROM permission_requests WHERE id = ?", (request_id,))
                updated_row = cur.fetchone()
                cur.execute("SELECT name FROM services WHERE id = ?", (updated_row["service_id"],))
                svc_row = cur.fetchone()
                svc_name = svc_row["name"] if svc_row else updated_row["service_id"]

                cur.execute("SELECT id, name FROM tools")
                tool_map = {r["id"]: r["name"] for r in cur.fetchall()}

                return _row_to_permission_request(
                    updated_row,
                    tool_map=tool_map,
                    service_name=svc_name
                )

        return await asyncio.to_thread(_sync_op)

    # --- 个人业务凭据管理 (User Credential Bindings) ---

    async def save_user_binding(
        self,
        user_id: str,
        service_id: str,
        credentials: Dict[str, Any],
        credential_schema: Optional[ServiceCredentialSchema] = None,
    ) -> UserServiceBinding:
        """加密保存或更新用户的特定服务业务凭据绑定（状态重置为 active，验证状态为 saved）"""
        from src.governance.crypto import decrypt_credentials, encrypt_credentials, generate_credential_summary

        now = _utc_now_iso()

        def _sync_op() -> UserServiceBinding:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, credential_version, encrypted_credentials FROM user_service_bindings WHERE user_id = ? AND service_id = ?",
                    (user_id, service_id),
                )
                row = cur.fetchone()

                merged_credentials = dict(credentials or {})
                if row and row["encrypted_credentials"]:
                    try:
                        existing_plain = decrypt_credentials(row["encrypted_credentials"])
                        for k, v in existing_plain.items():
                            if k not in merged_credentials or merged_credentials[k] in ("", None):
                                merged_credentials[k] = v
                    except Exception:
                        pass

                encrypted_data = encrypt_credentials(merged_credentials)
                summary_data = generate_credential_summary(merged_credentials)
                summary_json = json.dumps(summary_data, ensure_ascii=False)

                if row:
                    binding_id = row["id"]
                    new_version = row["credential_version"] + 1
                    cur.execute("""
                        UPDATE user_service_bindings
                        SET encrypted_credentials = ?, credential_summary = ?, credential_version = ?,
                            status = 'active', validation_status = 'saved', updated_at = ?
                        WHERE id = ?
                    """, (encrypted_data, summary_json, new_version, now, binding_id))
                else:
                    binding_id = f"usb_{uuid.uuid4().hex[:12]}"
                    new_version = 1
                    cur.execute("""
                        INSERT INTO user_service_bindings (id, user_id, service_id, encrypted_credentials, credential_summary, credential_version, status, validation_status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, 'active', 'saved', ?, ?)
                    """, (binding_id, user_id, service_id, encrypted_data, summary_json, new_version, now, now))
                conn.commit()

                return UserServiceBinding(
                    id=binding_id,
                    user_id=user_id,
                    service_id=service_id,
                    credential_summary=summary_data,
                    credential_version=new_version,
                    status="active",
                    validation_status="saved",
                    created_at=_parse_iso(now),
                    updated_at=_parse_iso(now),
                )

        return await asyncio.to_thread(_sync_op)

    async def get_user_binding(
        self, user_id: str, service_id: str
    ) -> Optional[UserServiceBinding]:
        """获取用户针对某服务的脱敏凭据绑定信息（绝对不包含密码）"""
        def _sync_op() -> Optional[UserServiceBinding]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM user_service_bindings WHERE user_id = ? AND service_id = ?",
                    (user_id, service_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                summary = {}
                try:
                    summary = json.loads(row["credential_summary"])
                except Exception:
                    pass
                keys = set(row.keys())
                return UserServiceBinding(
                    id=row["id"],
                    user_id=row["user_id"],
                    service_id=row["service_id"],
                    credential_summary=summary,
                    credential_version=row["credential_version"],
                    status=row["status"],
                    validation_status=row["validation_status"] if "validation_status" in keys and row["validation_status"] else ("unbound" if row["status"] == "unbound" else ("invalid" if row["status"] == "invalid" else "saved")),
                    created_at=_parse_iso(row["created_at"]),
                    updated_at=_parse_iso(row["updated_at"]),
                )

        return await asyncio.to_thread(_sync_op)

    async def get_decrypted_credentials(
        self, user_id: str, service_id: str
    ) -> Optional[Tuple[Dict[str, Any], int]]:
        """在受保护的服务端调用上下文解密凭据，返回 (credentials_dict, credential_version)"""
        from src.governance.crypto import decrypt_credentials

        def _sync_op() -> Optional[Tuple[Dict[str, Any], int]]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT encrypted_credentials, credential_version, status FROM user_service_bindings WHERE user_id = ? AND service_id = ?",
                    (user_id, service_id),
                )
                row = cur.fetchone()
                if not row or row["status"] != "active":
                    return None
                plain = decrypt_credentials(row["encrypted_credentials"])
                return plain, row["credential_version"]

        return await asyncio.to_thread(_sync_op)

    async def unbind_user_service(self, user_id: str, service_id: str) -> bool:
        """解绑凭据：置状态为 unbound 并递增版本号，使下游会话立即失效"""
        now = _utc_now_iso()

        def _sync_op() -> bool:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE user_service_bindings
                    SET status = 'unbound', validation_status = 'unbound', credential_version = credential_version + 1, updated_at = ?
                    WHERE user_id = ? AND service_id = ?
                """, (now, user_id, service_id))
                conn.commit()
                return cur.rowcount > 0

        return await asyncio.to_thread(_sync_op)

    async def update_binding_status(
        self, user_id: str, service_id: str, status: str, validation_status: Optional[str] = None
    ) -> bool:
        """更新凭据绑定状态与验证状态（如 verified / invalid）"""
        now = _utc_now_iso()
        val_status = validation_status or status

        def _sync_op() -> bool:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE user_service_bindings
                    SET status = ?, validation_status = ?, updated_at = ?
                    WHERE user_id = ? AND service_id = ?
                """, (status, val_status, now, user_id, service_id))
                conn.commit()
                return cur.rowcount > 0

        return await asyncio.to_thread(_sync_op)

    async def list_user_bindings(self, user_id: str) -> List[UserServiceBinding]:
        """查询用户当前所有的个人业务凭据绑定列表（脱敏）"""
        def _sync_op() -> List[UserServiceBinding]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM user_service_bindings WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,),
                )
                rows = cur.fetchall()
                results = []
                for r in rows:
                    summary = {}
                    try:
                        summary = json.loads(r["credential_summary"])
                    except Exception:
                        pass
                    keys = set(r.keys())
                    results.append(
                        UserServiceBinding(
                            id=r["id"],
                            user_id=r["user_id"],
                            service_id=r["service_id"],
                            credential_summary=summary,
                            credential_version=r["credential_version"],
                            status=r["status"],
                            validation_status=r["validation_status"] if "validation_status" in keys and r["validation_status"] else "saved",
                            created_at=_parse_iso(r["created_at"]),
                            updated_at=_parse_iso(r["updated_at"]),
                        )
                    )
                return results

        return await asyncio.to_thread(_sync_op)

    async def get_user_mcp_summary(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户'我添加的 MCP'综合状态视图 (ADR-011)

        聚合用户已获批工具、待审批工具、服务声明、当前个人凭据验证状态（已保存/已验证/登录失效/已解绑）与下游可达性
        """
        def _sync_op() -> List[Dict[str, Any]]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                # 1. 查询该用户的所有有效授权工具
                cur.execute("SELECT tool_id FROM user_grants WHERE user_id = ? AND status = 'active'", (user_id,))
                granted_tool_ids = {r["tool_id"] for r in cur.fetchall()}

                # 2. 查询该用户的所有待审批申请
                cur.execute(
                    "SELECT service_id, tool_ids FROM permission_requests WHERE user_id = ? AND status = 'pending'",
                    (user_id,),
                )
                pending_reqs = cur.fetchall()
                pending_tool_map: Dict[str, List[str]] = {}
                for pr in pending_reqs:
                    sid = pr["service_id"]
                    try:
                        tids = json.loads(pr["tool_ids"])
                    except Exception:
                        tids = []
                    pending_tool_map.setdefault(sid, []).extend(tids)

                # 3. 查询该用户的凭据绑定
                cur.execute("SELECT * FROM user_service_bindings WHERE user_id = ?", (user_id,))
                binding_rows = cur.fetchall()
                binding_map: Dict[str, sqlite3.Row] = {r["service_id"]: r for r in binding_rows}

                # 4. 统计涉及的所有服务 ID
                cur.execute("SELECT id, service_id, name, requires_credentials FROM tools")
                all_tools_map = {
                    r["id"]: (
                        r["service_id"],
                        r["name"],
                        bool(r["requires_credentials"]) if "requires_credentials" in r.keys() else False,
                    )
                    for r in cur.fetchall()
                }

                service_ids = set(binding_map.keys()) | set(pending_tool_map.keys())
                for gtid in granted_tool_ids:
                    if gtid in all_tools_map:
                        service_ids.add(all_tools_map[gtid][0])

                if not service_ids:
                    return []

                placeholders = ",".join(["?"] * len(service_ids))
                cur.execute(f"SELECT * FROM services WHERE id IN ({placeholders})", list(service_ids))
                service_rows = cur.fetchall()

                items = []
                for s_row in service_rows:
                    sid = s_row["id"]
                    svc = _row_to_service(s_row)
                    binding_row = binding_map.get(sid)

                    # 计算该用户在该服务下已获批/待审批的工具
                    approved_ids = [
                        gtid
                        for gtid in granted_tool_ids
                        if gtid in all_tools_map and all_tools_map[gtid][0] == sid
                    ]
                    pending_ids = [
                        ptid
                        for ptid in pending_tool_map.get(sid, [])
                        if ptid in all_tools_map and all_tools_map[ptid][0] == sid
                    ]
                    approved = [all_tools_map[gtid][1] for gtid in approved_ids]
                    pending = [all_tools_map[ptid][1] for ptid in pending_ids]

                    # 凭据要求落实到具体工具：仅当用户涉及的工具中有需凭据工具或用户已有绑定记录时，才判定需要凭据
                    any_user_tool_requires_cred = any(
                        all_tools_map[tid][2] for tid in (approved_ids + pending_ids)
                    )
                    requires_cred = bool(svc.credential_schema and svc.credential_schema.enabled) and (
                        any_user_tool_requires_cred or binding_row is not None
                    )
                    # 计算凭据状态: not_required / missing / unbound / invalid / saved / verified
                    if not requires_cred:
                        cred_status = "not_required"
                        cred_summary = {}
                        version = 0
                        up_at = None
                    elif not binding_row:
                        cred_status = "missing"
                        cred_summary = {}
                        version = 0
                        up_at = None
                    else:
                        b_keys = set(binding_row.keys())
                        b_status = binding_row["status"]
                        b_val = binding_row["validation_status"] if "validation_status" in b_keys and binding_row["validation_status"] else "saved"
                        if b_status == "unbound":
                            cred_status = "unbound"
                        elif b_status == "invalid" or b_val == "invalid":
                            cred_status = "invalid"
                        elif b_val == "verified":
                            cred_status = "verified"
                        else:
                            cred_status = "saved"
                        try:
                            cred_summary = json.loads(binding_row["credential_summary"])
                        except Exception:
                            cred_summary = {}
                        version = binding_row["credential_version"]
                        up_at = binding_row["updated_at"]

                    downstream_avail = "unavailable" if svc.status != ServiceStatus.ACTIVE else (svc.downstream_status or "available")

                    items.append({
                        "service_id": sid,
                        "service_name": svc.name,
                        "category": svc.category,
                        "endpoint_url": svc.endpoint_url,
                        "requires_credentials": requires_cred,
                        "credential_status": cred_status,
                        "service_status": svc.status.value,
                        "downstream_status": downstream_avail,
                        "downstream_error": svc.downstream_error,
                        "credential_summary": cred_summary,
                        "credential_version": version,
                        "approved_tools": approved,
                        "pending_tools": pending,
                        "updated_at": up_at,
                    })

                return items

        return await asyncio.to_thread(_sync_op)

    async def set_user_revocation(
        self,
        emp_no: str,
        is_active: bool,
        revoked_before: Optional[int] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        """写入或更新员工 JWT / ide-client Token 吊销与停用水位线"""
        now = _utc_now_iso()

        def _sync_op() -> Dict[str, Any]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT emp_no, is_active, revoked_before FROM user_revocations WHERE emp_no = ?",
                    (emp_no,),
                )
                existing = cur.fetchone()
                old_cutoff = int(existing["revoked_before"] or 0) if existing else 0
                if revoked_before is None:
                    new_cutoff = old_cutoff
                else:
                    new_cutoff = max(old_cutoff, int(revoked_before))

                active_int = 1 if is_active else 0
                if existing:
                    cur.execute(
                        """
                        UPDATE user_revocations
                        SET is_active = ?, revoked_before = ?, reason = ?, updated_at = ?
                        WHERE emp_no = ?
                        """,
                        (active_int, new_cutoff, reason, now, emp_no),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO user_revocations (emp_no, is_active, revoked_before, reason, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (emp_no, active_int, new_cutoff, reason, now),
                    )
                conn.commit()
                return {
                    "emp_no": emp_no,
                    "is_active": bool(active_int),
                    "revoked_before": new_cutoff,
                    "reason": reason,
                    "updated_at": now,
                }

        return await asyncio.to_thread(_sync_op)

    async def get_user_revocation(self, emp_no: str) -> Optional[Dict[str, Any]]:
        """查询员工本地吊销水位线记录"""
        def _sync_op() -> Optional[Dict[str, Any]]:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT emp_no, is_active, revoked_before, reason, updated_at FROM user_revocations WHERE emp_no = ?",
                    (emp_no,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "emp_no": row["emp_no"],
                    "is_active": bool(row["is_active"]),
                    "revoked_before": int(row["revoked_before"] or 0),
                    "reason": row["reason"] or "",
                    "updated_at": row["updated_at"],
                }

        return await asyncio.to_thread(_sync_op)

    async def is_token_revoked(self, emp_no: str, token_iat: int) -> bool:
        """检查用户是否被停用或 Token 签发时间早于吊销水位线"""
        if not emp_no or emp_no.lower() == "guest":
            return False
        rec = await self.get_user_revocation(emp_no)
        if not rec:
            return False
        if not rec["is_active"]:
            return True
        if rec["revoked_before"] > 0 and int(token_iat or 0) <= rec["revoked_before"]:
            return True
        return False
