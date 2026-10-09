"""任务执行器：平台与引擎的唯一交界面。

职责（规划 3 图执行器框）：
- 互斥锁：同刻仅允许一个引擎实例（进程内锁 + DB running 状态双重防护）；
- 子进程执行：cwd=run/{v}/，CONFIG_PATH/TRENDRADAR_HEADLESS 注入，
  stdout/stderr 重定向日志文件，崩溃与平台进程隔离；
- 结果落库：job_runs 记录状态/耗时/退出码/错误摘要。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import SETTINGS
from .database import get_session
from .events import broadcast
from .models import JobChannelResult, JobRun
from .projector import project_version

logger = logging.getLogger("webapp.runner")

_run_lock = threading.Lock()
_HARD_TIMEOUT_SECONDS = 1800


class JobConflictError(RuntimeError):
    """已有任务在运行时重复触发的冲突。"""


def _save_channel_results(job_id: int) -> None:
    """读取引擎写入的渠道送达结果（output/meta/notify_results.json）并落库。

    文件由本次任务产生（启动前已清理旧文件），读取后删除避免残留。

    Args:
        job_id: job_runs 记录 id。
    """
    path = SETTINGS.output_dir / "meta" / "notify_results.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("渠道结果文件解析失败", exc_info=True)
        return
    channels = data.get("channels", {})
    try:
        with get_session() as session:
            session.query(JobChannelResult).filter_by(job_run_id=job_id).delete()
            for channel, ok in channels.items():
                session.add(
                    JobChannelResult(
                        job_run_id=job_id,
                        channel=str(channel),
                        account_idx=0,
                        success=bool(ok),
                        batch_count=0,
                        error="" if ok else "发送失败（详见任务日志）",
                    )
                )
        logger.info("任务 #%s 渠道结果：%s", job_id, channels)
    except Exception:  # noqa: BLE001 结果落库失败不影响任务状态
        logger.exception("渠道结果落库失败")
    finally:
        path.unlink(missing_ok=True)


def _resolve_active_version_id() -> int | None:
    """读取当前生效配置版本 id。

    Returns:
        config_active 指向的版本 id；未初始化时返回 None。
    """
    from .models import ConfigActive

    with get_session() as session:
        active = session.query(ConfigActive).filter_by(owner_id=1).first()
        return active.current_version_id if active else None


def _read_active_content(version_id: int | None) -> str | None:
    """读取指定版本（默认当前生效版本）的 content JSON。

    Args:
        version_id: 配置版本 id，None 表示当前生效版本。

    Returns:
        content JSON 字符串；无版本时返回 None。
    """
    from .models import ConfigVersion

    with get_session() as session:
        if version_id is None:
            version_id = _resolve_active_version_id()
            if version_id is None:
                return None
        row = session.get(ConfigVersion, version_id)
        return row.content if row else None


def _tail_error(log_path: Path, limit: int = 3) -> str:
    """提取日志尾部若干非空行作为错误摘要。

    Args:
        log_path: 日志文件路径。
        limit: 保留行数。

    Returns:
        拼接后的摘要（最长 500 字符）。
    """
    try:
        lines = [ln.strip() for ln in log_path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        return " | ".join(lines[-limit:])[:500]
    except OSError:
        return ""


def _execute(job_id: int, version_id: int | None, version_no: int, run_dir: Path, log_path: Path) -> None:
    """在后台线程中流式执行引擎子进程：日志逐行落盘并实时广播。

    Args:
        job_id: job_runs 记录 id。
        version_id: 配置版本记录 id（可空，表示未初始化配置）。
        version_no: 配置版本号（用于日志目录命名）。
        run_dir: 子进程工作目录。
        log_path: 日志文件路径。
    """
    started = time.monotonic()
    deadline = started + _HARD_TIMEOUT_SECONDS
    env = {
        **os.environ,
        "CONFIG_PATH": str((run_dir / "config" / "config.yaml").resolve()),
        "FREQUENCY_WORDS_PATH": str((run_dir / "config" / "frequency_words.txt").resolve()),
        "TRENDRADAR_HEADLESS": "1",
        "PYTHONUNBUFFERED": "1",
    }
    exit_code: int | None = None
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "trendradar"],
            cwd=str(run_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        with open(log_path, "ab") as log_fh:
            for raw in iter(proc.stdout.readline, b""):
                log_fh.write(raw)
                log_fh.flush()
                broadcast({"type": "log", "job_id": job_id, "text": raw.decode("utf-8", errors="replace")})
                if time.monotonic() > deadline:
                    proc.kill()
                    exit_code = -9
                    break
            if exit_code is None:
                proc.wait(timeout=120)
                exit_code = proc.returncode
    except Exception as exc:  # noqa: BLE001 执行器需要兜底记录任意启动失败
        logger.exception("任务 %s 启动失败", job_id)
        with open(log_path, "ab") as log_fh:
            log_fh.write(f"[webapp] 引擎启动失败: {exc}\n".encode("utf-8"))
        exit_code = -1
    finally:
        if exit_code is None:
            exit_code = -1
        duration_ms = int((time.monotonic() - started) * 1000)
        status = "success" if exit_code == 0 else "failed"
        summary = "" if exit_code == 0 else _tail_error(log_path)
        _save_channel_results(job_id)
        try:
            with get_session() as session:
                job = session.get(JobRun, job_id)
                if job:
                    job.status = status
                    job.finished_at = datetime.now(timezone.utc)
                    job.duration_ms = duration_ms
                    job.exit_code = exit_code
                    job.error_summary = summary
        except Exception:
            logger.exception("任务 %s 结果落库失败", job_id)
        finally:
            broadcast({
                "type": "status",
                "job_id": job_id,
                "status": status,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            })
            _run_lock.release()
        logger.info("任务 #%s 完成 status=%s duration=%sms", job_id, status, duration_ms)


def trigger_job(trigger: str, config_version_id: int | None = None) -> JobRun:
    """触发一次引擎执行（cron / manual / api 统一入口）。

    Args:
        trigger: 触发方式（cron|manual|api）。
        config_version_id: 指定配置版本；None 使用当前生效版本。

    Returns:
        已创建的 JobRun 记录（running 状态）。

    Raises:
        JobConflictError: 已有任务运行中。
        RuntimeError: 配置尚未初始化（无任何版本）。
    """
    content = _read_active_content(config_version_id)
    if content is None:
        raise RuntimeError("配置尚未初始化，请先完成初始导入或保存")

    with get_session() as session:
        running = session.query(JobRun).filter_by(status="running").first()
        if running:
            raise JobConflictError(f"任务 #{running.id} 运行中，请稍后再试")

        from .models import ConfigVersion

        version_row = session.get(ConfigVersion, config_version_id) if config_version_id else None
        version_no = version_row.version if version_row else _current_version_no()
        job = JobRun(
            trigger=trigger,
            config_version_id=config_version_id or _resolve_active_version_id(),
            status="running",
        )
        session.add(job)
        session.flush()

        log_dir = SETTINGS.run_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"job-{job.id}.log"
        job.log_path = str(log_path)

    run_dir = project_version(version_no, content)

    # 清理上一次任务的渠道结果文件，确保落库的一定是本次任务产物
    (SETTINGS.output_dir / "meta" / "notify_results.json").unlink(missing_ok=True)

    acquired = _run_lock.acquire(blocking=False)
    if not acquired:  # DB 检查与锁之间的极小窗口兜底
        with get_session() as session:
            job = session.get(JobRun, job.id)
            if job:
                job.status = "failed"
                job.error_summary = "并发触发冲突"
        raise JobConflictError("并发触发冲突")

    log_path.write_text(
        f"[webapp] 任务 #{job.id} 触发={trigger} 配置=v{version_no} 时间={datetime.now()}\n",
        encoding="utf-8",
    )
    broadcast({"type": "status", "job_id": job.id, "status": "running", "trigger": trigger})
    threading.Thread(
        target=_execute,
        args=(job.id, config_version_id, version_no, run_dir, log_path),
        daemon=True,
        name=f"job-{job.id}",
    ).start()
    with get_session() as session:
        return session.get(JobRun, job.id)


def _current_version_no() -> int:
    """查询当前生效版本号（内部辅助）。

    Returns:
        版本号；未初始化返回 1。
    """
    from .models import ConfigActive, ConfigVersion

    with get_session() as session:
        active = session.query(ConfigActive).filter_by(owner_id=1).first()
        if active:
            row = session.get(ConfigVersion, active.current_version_id)
            if row:
                return row.version
    return 1


def read_job_log(job: JobRun, offset: int = 0) -> str:
    """读取任务日志（支持增量）。

    Args:
        job: 任务记录。
        offset: 起始字节偏移。

    Returns:
        日志文本片段。
    """
    path = Path(job.log_path)
    if not path.is_file():
        return ""
    data = path.read_bytes()
    return data[offset:].decode("utf-8", errors="replace")
