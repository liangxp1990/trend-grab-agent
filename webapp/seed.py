"""首次初始化（幂等）。

- ensure_admin：无用户时创建 admin（密码来自 WEB_ADMIN_PASSWORD）；
- ensure_config_v1：无配置版本时从引擎 config/ 目录导入为 v1 并设为生效；
- ensure_versions：刷新组件版本快照。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import SETTINGS
from .database import get_session
from .models import ConfigActive, ConfigVersion, User, VersionInfo
from .projector import MANAGED_FILES, compute_checksum, snapshot_from_dir
from .security import hash_password

logger = logging.getLogger("webapp.seed")


def ensure_admin() -> None:
    """确保 admin 用户存在（无用户表记录时创建）。"""
    with get_session() as session:
        if session.query(User).count() > 0:
            return
        session.add(
            User(username="admin", password_hash=hash_password(SETTINGS.admin_password), role="admin")
        )
    logger.info("已创建初始管理员 admin（请尽快修改默认密码）")


def ensure_config_v1() -> None:
    """从引擎 config/ 目录导入初始配置为 v1 并设为当前生效版本。"""
    with get_session() as session:
        if session.query(ConfigVersion).count() > 0:
            return
        snapshot = snapshot_from_dir()
        content_json = json.dumps(snapshot, ensure_ascii=False)
        version = ConfigVersion(
            owner_id=1,
            version=1,
            content=content_json,
            checksum=compute_checksum(content_json),
            comment="初始导入（来自 config/config.yaml）",
            created_by="system",
        )
        session.add(version)
        session.flush()
        session.add(ConfigActive(owner_id=1, current_version_id=version.id))
    logger.info("已导入初始配置 v1（含 %d 个配套文件）", len(MANAGED_FILES))


def ensure_versions() -> None:
    """刷新组件版本快照（引擎 / MCP / 平台）。"""
    root = Path(__file__).resolve().parent.parent

    def _read_version(fname: str) -> str:
        path = root / fname
        return path.read_text(encoding="utf-8").strip() if path.is_file() else "unknown"

    components = {
        "engine": _read_version("version"),
        "mcp": _read_version("version_mcp"),
        "webapp": "1.0.0",
    }
    with get_session() as session:
        for component, ver in components.items():
            row = session.query(VersionInfo).filter_by(component=component).first()
            if row:
                row.version = ver
            else:
                session.add(VersionInfo(component=component, version=ver))


def ensure_mcp_key() -> None:
    """确保共享卷存在 MCP 鉴权文件 config/mcp_auth.json（幂等生成）。

    MCP 容器以只读方式挂载同一 config/ 卷，读取此文件校验请求；
    Key 也可用 MCP_API_KEY 环境变量覆盖（优先级更高）。
    """
    import secrets

    auth_file = SETTINGS.config_dir / "mcp_auth.json"
    if auth_file.is_file():
        return
    auth_file.write_text(
        json.dumps({"api_key": secrets.token_hex(24)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("已生成 MCP API Key（config/mcp_auth.json）")


def run_seed() -> None:
    """执行全部幂等初始化。"""
    ensure_admin()
    ensure_config_v1()
    ensure_versions()
    ensure_mcp_key()
