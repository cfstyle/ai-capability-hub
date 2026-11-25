"""审计日志模块

记录工具调用的完整审计链路。MVP 输出结构化 JSON 日志。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("hub.audit")


class AuditLogger:
    """审计日志记录器

    MVP 阶段将审计事件写入结构化 JSON 日志（通过 Python logging）。
    后续可扩展为写入数据库、消息队列（Kafka）等。

    Usage::

        audit = AuditLogger()
        audit.log_tool_call(
            user_id="user-123",
            client_id="app-abc",
            tool_name="search",
            service_id="web-search",
            params_summary={"query": "hello"},
            result_status="success",
            duration_ms=42,
            trace_id="trace-xyz",
        )
    """

    def __init__(self, logger_name: str = "hub.audit") -> None:
        self._logger = logging.getLogger(logger_name)

    def log_tool_call(
        self,
        user_id: str,
        client_id: str,
        tool_name: str,
        service_id: str,
        params_summary: Optional[dict] = None,
        result_status: str = "unknown",
        duration_ms: Optional[float] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """记录一次工具调用的审计日志

        Args:
            user_id: 调用者用户 ID（来自 JWT sub）
            client_id: 客户端应用 ID
            tool_name: 工具命名空间名称（{service_id}__{tool_name}）
            service_id: 目标服务 ID
            params_summary: 调用参数摘要（脱敏后）
            result_status: 调用结果状态（success / error / timeout）
            duration_ms: 调用耗时（毫秒）
            trace_id: 分布式追踪 ID
        """
        event = {
            "event_type": "tool_call",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "client_id": client_id,
            "tool_name": tool_name,
            "service_id": service_id,
            "params_summary": params_summary,
            "result_status": result_status,
            "duration_ms": duration_ms,
            "trace_id": trace_id,
        }
        self._logger.info(json.dumps(event, ensure_ascii=False))

    # TODO: log_service_registration — 记录服务注册/更新事件
    # TODO: log_auth_event — 记录认证成功/失败事件
    # TODO: 支持批量写入和异步写入
