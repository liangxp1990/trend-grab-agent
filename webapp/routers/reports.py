"""报告中心路由：扫描 output/html 生成索引；静态报告经 /reports 挂载输出。"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter

from ..config import SETTINGS
from ..schemas import ReportItem
from ..security import CurrentUser

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

_TIME_STAMP_RE = re.compile(r"^(\d{2})-(\d{2})\.html$")


@router.get("", response_model=list[ReportItem])
def list_reports(current: CurrentUser, date: str = "") -> list[ReportItem]:
    """按日期列出历史报告（时间戳快照），新→旧。

    Args:
        date: 可选日期过滤（YYYY-MM-DD）。
    """
    html_root = SETTINGS.output_dir / "html"
    if not html_root.is_dir():
        return []
    items: list[ReportItem] = []
    for day_dir in sorted(html_root.iterdir(), reverse=True):
        if not day_dir.is_dir() or not re.match(r"^\d{4}-\d{2}-\d{2}$", day_dir.name):
            continue
        if date and day_dir.name != date:
            continue
        for report in sorted(day_dir.glob("*.html"), reverse=True):
            match = _TIME_STAMP_RE.match(report.name)
            if not match:
                continue
            hh, mm = match.groups()
            items.append(
                ReportItem(
                    date=day_dir.name,
                    time=f"{hh}:{mm}",
                    mode="current",
                    path=f"/reports/{day_dir.name}/{report.name}",
                )
            )
    return items[:500]


@router.get("/push-records")
def push_records(current: CurrentUser) -> list[dict]:
    """推送记录（period_executions 只读聚合，M2 起并入渠道结果）。"""
    from ..database import get_session
    from ..models import JobRun

    with get_session() as session:
        jobs = (
            session.query(JobRun)
            .filter(JobRun.status.in_(["success", "failed"]))
            .order_by(JobRun.id.desc())
            .limit(50)
            .all()
        )
        return [
            {
                "job_id": job.id,
                "trigger": job.trigger,
                "status": job.status,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "duration_ms": job.duration_ms,
            }
            for job in jobs
        ]
