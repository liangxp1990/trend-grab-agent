"""配置管理路由：读写、版本列表、回滚、调度定义。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..audit import record_audit
from ..database import get_session
from ..models import ConfigActive, ConfigVersion
from ..projector import compute_checksum, mask_sensitive
from ..schemas import ConfigPayload, RollbackResponse, ScheduleUpdate, VersionSummary
from ..scheduler import next_run_info, set_schedule
from ..security import CurrentUser

router = APIRouter(prefix="/api/v1/config", tags=["config"])


def _active_version_row(session) -> ConfigVersion | None:
    """查询当前生效版本记录。"""
    active = session.query(ConfigActive).filter_by(owner_id=1).first()
    if active is None:
        return None
    return session.get(ConfigVersion, active.current_version_id)


@router.get("")
def get_config(current: CurrentUser) -> dict:
    """返回当前生效配置（敏感值脱敏）。

    Raises:
        HTTPException: 尚未初始化配置时 404。
    """
    with get_session() as session:
        row = _active_version_row(session)
        if row is None:
            raise HTTPException(status_code=404, detail="配置尚未初始化")
        content = json.loads(row.content)
    return {
        "version": row.version,
        "version_id": row.id,
        "comment": row.comment,
        "created_at": row.created_at.isoformat(),
        "config": mask_sensitive(content.get("config", {})),
        "files": content.get("files", {}),
    }


@router.put("", response_model=VersionSummary)
def save_config(payload: ConfigPayload, request: Request, current: CurrentUser) -> VersionSummary:
    """保存配置为新版本并设为生效（下一任务起使用）。

    未修改的敏感字段以掩码提交，与当前生效版本合并还原真实值。

    Raises:
        HTTPException: 配置为空等校验错误。
    """
    from ..projector import merge_sensitive

    with get_session() as session:
        previous = _active_version_row(session)
        old_config = json.loads(previous.content).get("config", {}) if previous else {}
    merged_config = merge_sensitive(old_config, payload.config)

    content_json = json.dumps({"config": merged_config, "files": payload.files}, ensure_ascii=False)
    if not merged_config:
        raise HTTPException(status_code=422, detail="配置内容为空")
    with get_session() as session:
        latest = (
            session.query(ConfigVersion).filter_by(owner_id=1).order_by(ConfigVersion.version.desc()).first()
        )
        next_no = (latest.version + 1) if latest else 1
        version = ConfigVersion(
            owner_id=1,
            version=next_no,
            content=content_json,
            checksum=compute_checksum(content_json),
            comment=payload.comment or f"保存于 {datetime.now().strftime('%m-%d %H:%M')}",
            created_by=current.sub,
        )
        session.add(version)
        session.flush()
        active = session.query(ConfigActive).filter_by(owner_id=1).first()
        if active is None:
            session.add(ConfigActive(owner_id=1, current_version_id=version.id))
        else:
            active.current_version_id = version.id
        version_id, version_no = version.id, version.version
        created_at = version.created_at
    record_audit(request, current.sub, "config.save", f"新版本 v{next_no}：{payload.comment}")
    return VersionSummary(
        id=version_id,
        version=version_no,
        comment=payload.comment,
        created_by=current.sub,
        created_at=created_at or datetime.now(timezone.utc),
        is_active=True,
    )


@router.get("/versions", response_model=list[VersionSummary])
def list_versions(current: CurrentUser) -> list[VersionSummary]:
    """版本列表（新→旧，标注当前生效）。"""
    with get_session() as session:
        active = session.query(ConfigActive).filter_by(owner_id=1).first()
        active_id = active.current_version_id if active else None
        rows = (
            session.query(ConfigVersion)
            .filter_by(owner_id=1)
            .order_by(ConfigVersion.version.desc())
            .limit(100)
            .all()
        )
        return [
            VersionSummary(
                id=row.id,
                version=row.version,
                comment=row.comment,
                created_by=row.created_by,
                created_at=row.created_at,
                is_active=row.id == active_id,
            )
            for row in rows
        ]


@router.get("/versions/{version_id}/diff")
def version_diff(version_id: int, current: CurrentUser, against: int | None = None) -> dict:
    """版本对比：目标版本与其前一版本（或指定 against 版本）的配置树 diff。

    敏感值在 diff 中掩码展示；files 段仅列出变化的文件名。

    Raises:
        HTTPException: 版本不存在或缺少对比基准。
    """
    from ..projector import MASK_PREFIX, SENSITIVE_KEYS

    def flatten(node, prefix=""):
        result = {}
        if isinstance(node, dict):
            for k, v in node.items():
                result.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                result.update(flatten(v, f"{prefix}[{i}]"))
        else:
            result[prefix] = node
        return result

    def mask(path_key, value):
        leaf = path_key.rsplit(".", 1)[-1].split("[")[0]
        if leaf in SENSITIVE_KEYS and isinstance(value, str) and value:
            return MASK_PREFIX + value[-4:]
        return value

    with get_session() as session:
        row_a = session.get(ConfigVersion, version_id)
        if row_a is None:
            raise HTTPException(status_code=404, detail="目标版本不存在")
        if against is not None:
            row_b = session.get(ConfigVersion, against)
        else:
            row_b = (
                session.query(ConfigVersion)
                .filter(ConfigVersion.owner_id == 1, ConfigVersion.version < row_a.version)
                .order_by(ConfigVersion.version.desc())
                .first()
            )
        if row_b is None:
            raise HTTPException(status_code=404, detail="缺少对比基准（该版本没有更早的版本）")

        flat_a = flatten(json.loads(row_a.content).get("config", {}))
        flat_b = flatten(json.loads(row_b.content).get("config", {}))
        files_a = set(json.loads(row_a.content).get("files", {}).keys())
        files_b = set(json.loads(row_b.content).get("files", {}).keys())

    changes = []
    for key in sorted(set(flat_a) | set(flat_b)):
        va, vb = flat_a.get(key), flat_b.get(key)
        if va == vb:
            continue
        if vb is None:
            changes.append({"path": key, "kind": "added", "old": None, "new": mask(key, va)})
        elif va is None:
            changes.append({"path": key, "kind": "removed", "old": mask(key, vb), "new": None})
        else:
            changes.append({"path": key, "kind": "changed", "old": mask(key, vb), "new": mask(key, va)})

    return {
        "base": {"id": row_b.id, "version": row_b.version},
        "target": {"id": row_a.id, "version": row_a.version},
        "summary": {
            "added": sum(1 for c in changes if c["kind"] == "added"),
            "removed": sum(1 for c in changes if c["kind"] == "removed"),
            "changed": sum(1 for c in changes if c["kind"] == "changed"),
        },
        "files_added": sorted(files_a - files_b),
        "files_removed": sorted(files_b - files_a),
        "changes": changes[:300],
    }


@router.post("/versions/{version_id}/rollback", response_model=RollbackResponse)
def rollback(version_id: int, request: Request, current: CurrentUser) -> RollbackResponse:
    """回滚：将生效指针移到指定版本（创建一个指向同内容的新版本记录，保留完整链）。

    Raises:
        HTTPException: 目标版本不存在。
    """
    with get_session() as session:
        target = session.get(ConfigVersion, version_id)
        if target is None:
            raise HTTPException(status_code=404, detail="目标版本不存在")
        latest = (
            session.query(ConfigVersion).filter_by(owner_id=1).order_by(ConfigVersion.version.desc()).first()
        )
        next_no = (latest.version + 1) if latest else 1
        version = ConfigVersion(
            owner_id=1,
            version=next_no,
            content=target.content,
            checksum=target.checksum,
            comment=f"回滚至 v{target.version}",
            created_by=current.sub,
        )
        session.add(version)
        session.flush()
        active = session.query(ConfigActive).filter_by(owner_id=1).first()
        if active is None:
            session.add(ConfigActive(owner_id=1, current_version_id=version.id))
        else:
            active.current_version_id = version.id
        new_id, rolled_to = version.id, target.version
    record_audit(request, current.sub, "config.rollback", f"回滚到 v{rolled_to}")
    return RollbackResponse(rolled_back_to=rolled_to, new_version_id=new_id)


@router.get("/schedule")
def get_schedule(current: CurrentUser) -> dict:
    """读取调度定义（频率/启停/下次运行）。"""
    return next_run_info()


class TestAiPayload(BaseModel):
    """测试 AI 连通性请求（界面草稿值，无需先保存）。"""

    model: str = ""
    api_key: str = ""
    api_base: str = ""


@router.post("/test-ai")
def test_ai_connection(payload: TestAiPayload | None = None, current: CurrentUser = None) -> dict:
    """测试 AI 模型连通性（优先用界面草稿值；掩码/缺失回退生效版本真实值）。

    Args:
        payload: 界面当前填写的 model/api_key/api_base（可整体省略）。

    Returns:
        {"ok", "model", "latency_ms", "message"}。

    Raises:
        HTTPException: 模型/密钥未配置或调用失败。
    """
    import time

    import litellm

    from ..projector import MASK_PREFIX

    saved: dict = {}
    with get_session() as session:
        row = _active_version_row(session)
        if row is not None:
            saved = json.loads(row.content).get("config", {}).get("ai", {})

    body = payload or TestAiPayload()

    def resolve(field: str, draft: str) -> str:
        """草稿值优先；为空或掩码时回退生效版本真实值。"""
        if draft and not draft.startswith(MASK_PREFIX):
            return draft
        return str(saved.get(field, "") or "")

    model = resolve("model", body.model)
    api_key = resolve("api_key", body.api_key)
    api_base = resolve("api_base", body.api_base)

    if not model:
        raise HTTPException(status_code=422, detail="未配置模型（请填写 provider/model）")
    if not api_key:
        raise HTTPException(status_code=422, detail="未配置 API Key（填写后无需保存即可测试）")

    started = time.monotonic()
    try:
        response = litellm.completion(
            model=model,
            api_key=api_key,
            api_base=api_base or None,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            timeout=15,
        )
        return {
            "ok": True,
            "model": model,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "message": f"连接正常 · 返回 {len(response.choices)} 条响应",
        }
    except Exception as exc:  # noqa: BLE001 需要把提供商错误透传给用户
        raise HTTPException(status_code=502, detail=f"连接失败: {exc}") from exc


@router.put("/schedule")
def update_schedule(payload: ScheduleUpdate, request: Request, current: CurrentUser) -> dict:
    """更新调度频率与启停（热生效）。

    Raises:
        HTTPException: cron 表达式非法。
    """
    try:
        set_schedule(payload.cron_expr, payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(request, current.sub, "config.schedule", f"{payload.cron_expr} enabled={payload.enabled}")
    return next_run_info()
