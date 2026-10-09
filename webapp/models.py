"""平台库 ORM 模型。

按规划第 5 节数据模型实现；所有业务表带 owner_id（默认 1），
为多用户演进预留（D6 决策：结构性预留，不提前实现功能）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """UTC 当前时间（存储统一使用 UTC，展示层转时区）。"""
    return datetime.now(timezone.utc)


class User(Base):
    """平台用户。一期仅一条 admin 记录；role 为 RBAC 预留。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="admin", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConfigVersion(Base):
    """配置版本（配置真相源）。

    content 存引擎 config.yaml 的完整结构化 JSON（含 timeline 段）；
    secrets_key 为敏感项加密预留列（M3 启用 Fernet）。
    """

    __tablename__ = "config_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    secrets_cipher: Mapped[str] = mapped_column(Text, default="", nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    comment: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("owner_id", "version", name="uq_config_version"),)


class ConfigActive(Base):
    """当前生效配置版本指针（每 owner 一行）。"""

    __tablename__ = "config_active"

    owner_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("config_versions.id"), nullable=False
    )


class JobRun(Base):
    """任务级执行记录（区别于引擎数据层的 crawl_records）。"""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)  # cron | manual | api
    config_version_id: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int] = mapped_column(Integer, nullable=True)
    error_summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    log_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    channel_results: Mapped[list["JobChannelResult"]] = relationship(
        back_populates="job_run", cascade="all, delete-orphan"
    )


class JobChannelResult(Base):
    """各通知渠道送达结果（执行器解析引擎输出后落库）。"""

    __tablename__ = "job_channel_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    account_idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    batch_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str] = mapped_column(String(300), default="", nullable=False)

    job_run: Mapped[JobRun] = relationship(back_populates="channel_results")


class AuditLog(Base):
    """变更审计：记录动作与目标，不记录敏感值。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ip: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScheduleDef(Base):
    """平台调度定义（触发频率），一期单条记录。"""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str] = mapped_column(String(16), default="", nullable=False)


class VersionInfo(Base):
    """组件版本快照（system/status 展示用，启动时刷新）。"""

    __tablename__ = "version_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RefreshToken(Base):
    """预留：刷新令牌表（一期仅访问令牌，短期无需）。"""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
