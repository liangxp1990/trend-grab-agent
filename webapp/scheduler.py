"""内置调度器（APScheduler cron 封装）。

实现规划 D3：调度必须可 introspect——next_run_at 持久化到 schedules 表，
UI 可展示"下次运行时间 / 启停 / 立即执行"。触发统一走 runner.trigger_job，
与手动触发同一条互斥路径。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .database import get_session
from .models import ScheduleDef
from .runner import JobConflictError, trigger_job

logger = logging.getLogger("webapp.scheduler")

_scheduler: AsyncIOScheduler | None = None
JOB_ID = "trendradar-crawl"


def get_scheduler() -> AsyncIOScheduler:
    """返回调度器单例（未启动状态）。

    Returns:
        AsyncIOScheduler 实例。
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    return _scheduler


def _persist_next_run() -> None:
    """将调度器计算的下次触发时间回写 schedules 表。"""
    job = get_scheduler().get_job(JOB_ID)
    if job is None:
        return
    with get_session() as session:
        row = session.query(ScheduleDef).filter_by(name="default").first()
        if row:
            row.next_run_at = job.next_run_time


async def _run_crawl() -> None:
    """cron 回调：触发一次引擎执行并更新调度状态。"""
    try:
        job = trigger_job("cron")
        logger.info("调度触发任务 #%s", job.id)
    except JobConflictError as exc:
        logger.warning("调度触发被跳过：%s", exc)
    except Exception:  # noqa: BLE001 调度回调必须吞异常保活
        logger.exception("调度触发失败")
    finally:
        with get_session() as session:
            row = session.query(ScheduleDef).filter_by(name="default").first()
            if row:
                row.last_run_status = "triggered"


def start_scheduler() -> None:
    """启动调度器：读取 schedules 表（无则按环境变量默认建一条）并注册 cron。

    Raises:
        ValueError: cron 表达式非法。
    """
    with get_session() as session:
        row = session.query(ScheduleDef).filter_by(name="default").first()
        if row is None:
            from .config import SETTINGS

            row = ScheduleDef(name="default", cron_expr=SETTINGS.cron_expr, enabled=True)
            session.add(row)
            session.flush()
        cron_expr, enabled = row.cron_expr, row.enabled

    scheduler = get_scheduler()
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
    if enabled:
        scheduler.add_job(
            _run_crawl,
            CronTrigger.from_crontab(cron_expr),
            id=JOB_ID,
            name="TrendRadar 定时采集",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("调度已启用: %s", cron_expr)
    if not scheduler.running:
        scheduler.start()
    _persist_next_run()


def set_schedule(cron_expr: str, enabled: bool) -> None:
    """更新调度定义并热生效。

    Args:
        cron_expr: 新 cron 表达式（5 段）。
        enabled: 是否启用。

    Raises:
        ValueError: 表达式非法或调度器未启动。
    """
    scheduler = get_scheduler()
    try:
        CronTrigger.from_crontab(cron_expr)
    except ValueError as exc:
        raise ValueError(f"cron 表达式非法: {exc}") from exc

    with get_session() as session:
        row = session.query(ScheduleDef).filter_by(name="default").first()
        if row is None:
            row = ScheduleDef(name="default", cron_expr=cron_expr, enabled=enabled)
            session.add(row)
        else:
            row.cron_expr = cron_expr
            row.enabled = enabled

    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
    if enabled and scheduler.running:
        scheduler.add_job(
            _run_crawl,
            CronTrigger.from_crontab(cron_expr),
            id=JOB_ID,
            replace_existing=True,
        )
    _persist_next_run()


def next_run_info() -> dict[str, str | None | bool]:
    """读取调度当前状态（UI 展示）。

    Returns:
        {"enabled", "cron", "next_run"} 摘要。
    """
    with get_session() as session:
        row = session.query(ScheduleDef).filter_by(name="default").first()
        if row is None:
            return {"enabled": False, "cron": "", "next_run": None}
        nxt: datetime | None = row.next_run_at
        return {
            "enabled": row.enabled,
            "cron": row.cron_expr,
            "next_run": nxt.astimezone(timezone.utc).isoformat() if nxt else None,
        }
