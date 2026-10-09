"""webapp 运行配置。

全部来自环境变量，遵循规划"敏感信息走 env"原则：
- WEB_SECRET_KEY      JWT 签名密钥（必填，缺省时自动生成仅限开发）
- WEB_ADMIN_PASSWORD  初始管理员密码（首次初始化用户时使用）
- WEB_DB_PATH         平台库 SQLite 路径（默认 <项目根>/data/platform.db）
- WEB_CRON            调度 cron 表达式（默认 */30 * * * *）
- WEB_RUN_DIR         配置投影与任务日志根目录（默认 <项目根>/data/run）
- WEB_OUTPUT_DIR      引擎 output 目录（默认 <项目根>/output）
- WEB_CONFIG_DIR      引擎 config 目录（默认 <项目根>/config）
- WEB_TOKEN_EXPIRE_H  JWT 有效期小时数（默认 24）
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from dataclasses import dataclass


def _project_root() -> Path:
    """返回项目根目录（webapp 包的上一级）。"""
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class WebAppSettings:
    """不可变的 webapp 配置集合（启动时构建一次）。

    Attributes:
        secret_key: JWT 签名密钥。
        admin_password: 初始管理员密码。
        db_path: 平台库 SQLite 文件路径。
        run_dir: 投影/日志根目录。
        output_dir: 引擎数据输出目录。
        config_dir: 引擎配置目录（含词表与提示词）。
        cron_expr: 内置调度器的 cron 表达式。
        token_expire_hours: JWT 有效期（小时）。
    """

    secret_key: str
    admin_password: str
    db_path: Path
    run_dir: Path
    output_dir: Path
    config_dir: Path
    cron_expr: str
    token_expire_hours: int


def load_settings() -> WebAppSettings:
    """从环境变量构建 WebAppSettings，并确保所需目录存在。

    Returns:
        冻结的配置对象。
    """
    root = _project_root()
    db_path = Path(os.environ.get("WEB_DB_PATH", str(root / "data" / "platform.db")))
    run_dir = Path(os.environ.get("WEB_RUN_DIR", str(root / "data" / "run")))
    settings = WebAppSettings(
        secret_key=os.environ.get("WEB_SECRET_KEY", "") or secrets.token_hex(32),
        admin_password=os.environ.get("WEB_ADMIN_PASSWORD", "") or "trendradar",
        db_path=db_path,
        run_dir=run_dir,
        output_dir=Path(os.environ.get("WEB_OUTPUT_DIR", str(root / "output"))),
        config_dir=Path(os.environ.get("WEB_CONFIG_DIR", str(root / "config"))),
        cron_expr=os.environ.get("WEB_CRON", "*/30 * * * *"),
        token_expire_hours=int(os.environ.get("WEB_TOKEN_EXPIRE_H", "24")),
    )
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.run_dir.mkdir(parents=True, exist_ok=True)
    return settings


SETTINGS: WebAppSettings = load_settings()
