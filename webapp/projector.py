"""配置投影器：DB 版本 → 引擎可执行的文件集。

实现规划 D2 决策（DB → YAML 投影 + 子进程执行）与复盘补丁 1
（投影器双写共享卷，保证 MCP / CLI 与平台读到同一份最新配置）：

1. 生效投影：写入 run/{version}/config/{完整文件集}，任务执行期冻结；
2. 双写共享卷：同步写入引擎 config/ 目录（config.yaml 与全部配套文件），
   使 trendradar-mcp 容器与 CLI 回退模式零改造读到最新配置。

content JSON 结构：
    {"config": {…config.yaml 主结构…},
     "files": {"timeline.yaml": "…", "frequency_words.txt": "…", …}}
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from .config import SETTINGS

logger = logging.getLogger("webapp.projector")

# 投影文件集白名单：config/ 目录中随配置版本管理的文件（相对路径）
MANAGED_FILES: tuple[str, ...] = (
    "timeline.yaml",
    "frequency_words.txt",
    "ai_interests.txt",
    "ai_analysis_prompt.txt",
    "ai_translation_prompt.txt",
    "ai_filter/prompt.txt",
    "ai_filter/extract_prompt.txt",
    "ai_filter/update_tags_prompt.txt",
)

# 敏感键（API 层脱敏展示用；投影时必须写真实值）
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {"webhook_url", "bot_token", "chat_id", "password", "api_key", "token", "url", "secret_access_key"}
)


def compute_checksum(content_json: str) -> str:
    """计算配置内容校验和（SHA-256），用于版本比对与幂等判断。

    Args:
        content_json: 序列化后的配置 JSON 字符串。

    Returns:
        十六进制摘要。
    """
    return hashlib.sha256(content_json.encode("utf-8")).hexdigest()


def mask_sensitive(node: Any) -> Any:
    """递归脱敏配置树中的敏感值（仅保留尾 4 位），用于 API 返回。

    Args:
        node: 任意配置子树。

    Returns:
        脱敏后的新树（不修改原对象，遵循不可变原则）。
    """
    if isinstance(node, dict):
        return {
            k: ("••••" + str(v)[-4:] if isinstance(v, str) and v and k in SENSITIVE_KEYS else mask_sensitive(v))
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [mask_sensitive(item) for item in node]
    return node


MASK_PREFIX = "••••"


def merge_sensitive(old: Any, new: Any) -> Any:
    """保存时合并：新值为脱敏掩码（未被用户修改）则回退旧真实值。

    前端编辑基于脱敏视图：用户未触碰的敏感字段仍呈掩码形态，
    直接落库会把掩码写成真实凭据。此函数递归还原。

    Args:
        old: 旧配置子树（含真实值）。
        new: 新配置子树（可能含掩码）。

    Returns:
        合并后的新树（不修改入参）。
    """
    if isinstance(new, dict) and isinstance(old, dict):
        return {k: merge_sensitive(old.get(k), v) for k, v in new.items()}
    if isinstance(new, list) and isinstance(old, list):
        return [merge_sensitive(o, n) for o, n in zip(old, new)] + new[len(old):]
    if isinstance(new, str) and new.startswith(MASK_PREFIX) and old is not None:
        return old
    return new


def snapshot_from_dir() -> dict[str, Any]:
    """从引擎 config/ 目录读取当前文件集，打包为 content 结构（seed 导入用）。

    Returns:
        {"config": 解析后的 yaml 主结构, "files": {相对路径: 文本内容}}。
    """
    config_file = SETTINGS.config_dir / "config.yaml"
    with open(config_file, "r", encoding="utf-8") as fh:
        parsed = yaml.safe_load(fh) or {}
    files: dict[str, str] = {}
    for rel in MANAGED_FILES:
        path = SETTINGS.config_dir / rel
        if path.is_file():
            files[rel] = path.read_text(encoding="utf-8")
    return {"config": parsed, "files": files}


def _write_fileset(target_dir: Path, content: dict[str, Any], full_replace: bool = True) -> None:
    """将 content 结构写为完整文件集。

    Args:
        target_dir: 目标 config 目录。
        content: {"config": dict, "files": {rel: text}}。
        full_replace: True 时整目录原子替换（run 投影，快照语义）；
            False 时仅逐文件覆盖受管文件（共享卷双写），
            保留用户目录中的其他文件（如 config/custom/）。
    """
    if not full_replace:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "config.yaml").write_text(
            yaml.safe_dump(content.get("config", {}), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        for rel, text in content.get("files", {}).items():
            dest = target_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        return

    tmp_dir = target_dir.parent / (target_dir.name + ".tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    (tmp_dir / "config.yaml").write_text(
        yaml.safe_dump(content.get("config", {}), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    for rel, text in content.get("files", {}).items():
        dest = tmp_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    tmp_dir.rename(target_dir)


def _localize_paths(content: dict[str, Any]) -> dict[str, Any]:
    """将引擎存储路径本地化为共享 output 绝对路径。

    引擎以 cwd=run/{v}/ 运行，storage.local.data_dir 默认是相对路径
    "output"，会导致数据日库与 HTML 报告落在投影目录内而非共享卷。
    投影时改写为平台配置的 output 绝对路径（不修改入参，返回新树）。

    Args:
        content: 原始 content 结构。

    Returns:
        路径本地化后的新 content。
    """
    config = dict(content.get("config", {}))
    storage = dict(config.get("storage", {}))
    local = dict(storage.get("local", {}))
    local["data_dir"] = str(SETTINGS.output_dir.resolve())
    storage["local"] = local
    config["storage"] = storage
    return {**content, "config": config}


def project_version(version: int, content_json: str) -> Path:
    """将指定配置版本投影为执行目录，并双写共享卷。

    Args:
        version: 配像版本号。
        content_json: content 结构的 JSON 字符串。

    Returns:
        版本运行目录（run/{version}，子进程 cwd）。

    Raises:
        ValueError: content JSON 解析失败。
    """
    try:
        content = _localize_paths(json.loads(content_json))
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置内容非法 JSON: {exc}") from exc

    run_dir = SETTINGS.run_dir / f"v{version}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # output 符号链接：引擎多处硬编码相对路径 "output"（HTML 报告、meta、
    # 根 index 等），统一以符号链接导入共享卷，产物天然落位且零引擎改动；
    # symlink 不可用时退回 data_dir 本地化方案（见 _localize_paths）。
    output_link = run_dir / "output"
    try:
        if output_link.is_symlink() or output_link.exists():
            if output_link.is_symlink() or output_link.is_file():
                output_link.unlink()
            else:
                shutil.rmtree(output_link)
        os.symlink(SETTINGS.output_dir.resolve(), output_link, target_is_directory=True)
    except OSError:
        logger.warning("output 符号链接创建失败，依赖 data_dir 本地化兜底", exc_info=True)

    _write_fileset(run_dir / "config", content)

    # 双写共享卷：MCP / CLI 与平台读到同一份当前配置（复盘补丁 1）。
    # 逐文件覆盖（full_replace=False），不触碰共享目录中的其他文件。
    try:
        _write_fileset(SETTINGS.config_dir, content, full_replace=False)
    except OSError as exc:  # 共享卷只读等场景不阻塞任务执行
        logger.warning("共享卷双写失败（MCP/CLI 将读到旧配置）: %s", exc)

    # 敏感投影权限收紧（复盘补丁 2 的文件层缓解）
    try:
        os.chmod(run_dir, 0o700)
        for path in run_dir.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o600)
    except OSError:
        logger.debug("权限设置跳过（非 POSIX 或权限不足）")
    return run_dir


def cleanup_version_dir(version: int, keep_deidentified: bool = True) -> None:
    """任务结束后清理敏感投影（保留脱敏副本供排障）。

    Args:
        version: 配置版本号。
        keep_deidentified: True 时以脱敏内容重建一份副本。
    """
    run_dir = SETTINGS.run_dir / f"v{version}"
    if not run_dir.exists():
        return
    if keep_deidentified:
        masked_config = run_dir / "config" / "config.yaml"
        if masked_config.is_file():
            try:
                parsed = yaml.safe_load(masked_config.read_text(encoding="utf-8")) or {}
                masked_config.write_text(
                    yaml.safe_dump(mask_sensitive(parsed), allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
            except yaml.YAMLError:
                pass
    shutil.rmtree(run_dir, ignore_errors=True)
