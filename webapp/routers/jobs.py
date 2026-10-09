"""任务路由：列表、手动触发、详情、日志增量读取。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..audit import record_audit
from ..database import get_session
from ..models import JobChannelResult, JobRun
from ..runner import JobConflictError, read_job_log, trigger_job
from ..schemas import JobSummary, TriggerRequest
from ..security import CurrentUser

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=list[JobSummary])
def list_jobs(
    current: CurrentUser,
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[JobSummary]:
    """任务历史（分页，可按状态过滤）。"""
    with get_session() as session:
        query = session.query(JobRun).order_by(JobRun.id.desc())
        if status:
            query = query.filter_by(status=status)
        rows = query.offset(offset).limit(limit).all()
        return [
            JobSummary(
                id=row.id,
                trigger=row.trigger,
                status=row.status,
                started_at=row.started_at,
                finished_at=row.finished_at,
                duration_ms=row.duration_ms,
                exit_code=row.exit_code,
                error_summary=row.error_summary,
                config_version_id=row.config_version_id,
                channels_ok=sum(1 for ch in row.channel_results if ch.success),
                channels_total=len(row.channel_results),
            )
            for row in rows
        ]


@router.post("/trigger", response_model=JobSummary, status_code=202)
def trigger(payload: TriggerRequest, request: Request, current: CurrentUser) -> JobSummary:
    """手动触发一次引擎执行。

    Raises:
        HTTPException: 冲突 409 / 未初始化 409。
    """
    try:
        job = trigger_job("manual", payload.config_version_id)
    except JobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_audit(request, current.sub, "job.trigger", f"任务 #{job.id}")
    return JobSummary(
        id=job.id,
        trigger=job.trigger,
        status=job.status,
        started_at=job.started_at,
        finished_at=None,
        duration_ms=None,
        exit_code=None,
        error_summary="",
        config_version_id=job.config_version_id,
    )


@router.get("/{job_id}")
def job_detail(job_id: int, current: CurrentUser) -> dict:
    """任务详情（含渠道送达结果，M2 起由执行器解析回填）。"""
    with get_session() as session:
        row = session.get(JobRun, job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        channels = [
            {"channel": ch.channel, "account": ch.account_idx, "success": ch.success, "batches": ch.batch_count, "error": ch.error}
            for ch in row.channel_results
        ]
        return {
            "id": row.id,
            "trigger": row.trigger,
            "status": row.status,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "duration_ms": row.duration_ms,
            "exit_code": row.exit_code,
            "error_summary": row.error_summary,
            "log_path": row.log_path,
            "config_version_id": row.config_version_id,
            "channels": channels,
        }


@router.get("/{job_id}/logs")
def job_logs(
    job_id: int,
    current: CurrentUser,
    offset: int = Query(default=0, ge=0),
) -> dict:
    """增量读取任务日志（前端轮询拼接）。

    Raises:
        HTTPException: 任务不存在。
    """
    with get_session() as session:
        row = session.get(JobRun, job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        chunk = read_job_log(row, offset)
        return {"offset": offset, "next_offset": offset + len(chunk.encode("utf-8")), "text": chunk}
