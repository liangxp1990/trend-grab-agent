"""API 请求/响应模型（Pydantic）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """登录成功响应。"""

    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class ConfigPayload(BaseModel):
    """保存配置请求：完整 content 结构（config 主结构 + 配套文件）。"""

    config: dict[str, Any]
    files: dict[str, str] = Field(default_factory=dict)
    comment: str = Field(default="", max_length=200)


class VersionSummary(BaseModel):
    """配置版本摘要（不含内容）。"""

    id: int
    version: int
    comment: str
    created_by: str
    created_at: datetime
    is_active: bool = False


class RollbackResponse(BaseModel):
    """回滚结果。"""

    rolled_back_to: int
    new_version_id: int


class TriggerRequest(BaseModel):
    """手动触发请求。"""

    config_version_id: int | None = None


class JobSummary(BaseModel):
    """任务记录摘要。"""

    id: int
    trigger: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    exit_code: int | None
    error_summary: str
    config_version_id: int | None
    channels_ok: int = 0
    channels_total: int = 0


class ScheduleUpdate(BaseModel):
    """调度更新请求。"""

    cron_expr: str = Field(min_length=9, max_length=64)
    enabled: bool = True


class NewsItem(BaseModel):
    """热榜条目（只读查询日库）。"""

    id: int
    title: str
    platform: str
    rank: int
    crawl_count: int
    first_crawl_time: str | None
    last_crawl_time: str | None
    url: str


class NewsPage(BaseModel):
    """热榜分页结果。"""

    total: int
    items: list[NewsItem]


class ReportItem(BaseModel):
    """历史报告条目。"""

    date: str
    time: str
    mode: str
    path: str


class SystemStatus(BaseModel):
    """系统状态摘要。"""

    versions: dict[str, str]
    schedule: dict[str, Any]
    today_jobs: int
    today_success: int
    output_bytes: int
    output_dir: str
