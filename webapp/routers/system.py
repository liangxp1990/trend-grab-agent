"""系统状态路由。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from ..config import SETTINGS
from ..database import get_session
from ..models import JobRun, VersionInfo
from ..scheduler import next_run_info
from ..schemas import SystemStatus
from ..security import CurrentUser

router = APIRouter(prefix="/api/v1/system", tags=["system"])


def _dir_size(path) -> int:
    """递归统计目录字节数。"""
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else 0


@router.get("/status", response_model=SystemStatus)
def system_status(current: CurrentUser) -> SystemStatus:
    """版本、调度、今日任务与存储用量摘要。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_session() as session:
        versions = {row.component: row.version for row in session.query(VersionInfo).all()}
        today_jobs = session.query(JobRun).filter(JobRun.started_at >= today).count()
        today_success = (
            session.query(JobRun)
            .filter(JobRun.started_at >= today, JobRun.status == "success")
            .count()
        )
    return SystemStatus(
        versions=versions,
        schedule=next_run_info(),
        today_jobs=today_jobs,
        today_success=today_success,
        output_bytes=_dir_size(SETTINGS.output_dir),
        output_dir=str(SETTINGS.output_dir),
    )


@router.get("/storage")
def storage_status(current: CurrentUser) -> dict:
    """存储后端状态（本地 SQLite 用量/库数 + 远程 S3 配置检测）。"""
    news_dir = SETTINGS.output_dir / "news"
    db_files = sorted(news_dir.glob("*.db")) if news_dir.is_dir() else []
    remote_configured = all(
        os.environ.get(key, "").strip()
        for key in ("S3_ENDPOINT_URL", "S3_BUCKET_NAME", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
    )
    with get_session() as session:
        from ..models import ConfigActive, ConfigVersion

        active = session.query(ConfigActive).filter_by(owner_id=1).first()
        retention = "永久保留"
        backend = "local"
        if active:
            row = session.get(ConfigVersion, active.current_version_id)
            if row:
                content = json.loads(row.content)
                storage_cfg = content.get("config", {}).get("storage", {})
                backend = storage_cfg.get("backend", "auto")
                retention = f"{storage_cfg.get('local', {}).get('retention_days', 0)} 天（0=永久）"
    return {
        "backend": backend,
        "local": {
            "db_count": len(db_files),
            "latest_db": db_files[-1].stem if db_files else "",
            "bytes": _dir_size(SETTINGS.output_dir),
            "retention": retention,
        },
        "remote": {"configured": remote_configured, "note": "S3 兼容（R2/OSS/COS/MinIO）"},
    }


@router.get("/mcp-key")
def get_mcp_key(current: CurrentUser) -> dict:
    """读取 MCP API Key（含来源判定；MCP_API_KEY 环境变量优先时文件值不生效）。"""
    auth_file = SETTINGS.config_dir / "mcp_auth.json"
    file_key = ""
    if auth_file.is_file():
        try:
            file_key = json.loads(auth_file.read_text(encoding="utf-8")).get("api_key", "")
        except (OSError, ValueError):
            file_key = ""
    env_key = os.environ.get("MCP_API_KEY", "").strip()
    return {
        "api_key": env_key or file_key,
        "source": "env" if env_key else ("file" if file_key else "none"),
        "note": "MCP 容器重启后生效；客户端以 Authorization: Bearer 或 X-API-Key 携带",
    }


@router.post("/mcp-key/regenerate")
def regenerate_mcp_key(request: Request, current: CurrentUser) -> dict:
    """重新生成 MCP API Key（写入共享卷；旧 Key 立即失效于容器重启后）。"""
    import secrets

    from ..audit import record_audit

    auth_file = SETTINGS.config_dir / "mcp_auth.json"
    new_key = secrets.token_hex(24)
    auth_file.write_text(
        json.dumps({"api_key": new_key}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    record_audit(request, current.sub, "config.mcp_key_regen", "MCP API Key 已重新生成")
    return {"api_key": new_key, "note": "已写入共享卷；MCP 容器需重启以加载新 Key"}


@router.get("/audit-logs")
def audit_logs(
    current: CurrentUser,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """审计日志（时间倒序，分页）。"""
    from ..models import AuditLog

    with get_session() as session:
        rows = (
            session.query(AuditLog)
            .order_by(AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        total = session.query(AuditLog).count()
    return {
        "total": total,
        "items": [
            {
                "time": row.created_at.isoformat(),
                "username": row.username,
                "action": row.action,
                "detail": row.detail,
                "ip": row.ip,
            }
            for row in rows
        ],
    }
