"""审计日志辅助：所有变更动作统一走此入口，不记录敏感值。"""

from __future__ import annotations

from fastapi import Request

from .database import get_session
from .models import AuditLog
from .security import client_ip


def record_audit(request: Request | None, username: str, action: str, detail: str = "") -> None:
    """写入一条审计日志（失败不阻断主流程）。

    Args:
        request: 触发请求（可为 None，如调度器内部动作）。
        username: 操作者。
        action: 动作标识（config.save / job.trigger / auth.login …）。
        detail: 动作描述（不得包含敏感值）。
    """
    try:
        with get_session() as session:
            session.add(
                AuditLog(
                    username=username,
                    action=action,
                    detail=detail[:2000],
                    ip=client_ip(request) if request else "system",
                )
            )
    except Exception:  # noqa: BLE001 审计失败仅记日志
        import logging

        logging.getLogger("webapp.audit").exception("审计写入失败 action=%s", action)
