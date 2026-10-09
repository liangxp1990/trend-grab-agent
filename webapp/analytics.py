"""分析能力适配层：复用 MCP 的 AnalyticsTools（同源口径，零重构）。

规划 D4 决策：MCP 与 Web 的分析逻辑共享同一实现。本模块持有
AnalyticsTools 单例并做轻量形态转换——MCP 侧代码保持不动，
Web 端口径与 27 个 MCP 工具严格一致。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("webapp.analytics")

_tools: "AnalyticsTools | None" = None


def get_analytics_tools() -> "AnalyticsTools":
    """返回 AnalyticsTools 单例（懒初始化）。

    Returns:
        mcp_server.tools.analytics.AnalyticsTools 实例。
    """
    global _tools
    if _tools is None:
        from mcp_server.tools.analytics import AnalyticsTools

        project_root = str(Path(__file__).resolve().parent.parent)
        _tools = AnalyticsTools(project_root)
        logger.info("AnalyticsTools 已初始化（project_root=%s）", project_root)
    return _tools


def unwrap(result: dict[str, Any]) -> dict[str, Any]:
    """把 MCP 工具的标准返回（success/summary/data）解包为 Web API 形态。

    Args:
        result: AnalyticsTools 方法的返回 Dict。

    Returns:
        {"ok", "summary", "data"}；异常信息附带 message。

    Raises:
        ValueError: 工具执行失败（success=False）。
    """
    if not result.get("success", False):
        raise ValueError(result.get("message", "分析工具执行失败"))
    return {
        "ok": True,
        "summary": result.get("summary", {}),
        "data": result.get("data", []),
        "message": result.get("message", ""),
    }


def viral_topics(threshold: float = 3.0, time_window: int = 24) -> dict[str, Any]:
    """异常爆火话题检测（与 MCP detect_viral_topics 同源）。

    Args:
        threshold: 热度突增倍数阈值。
        time_window: 检测时间窗口（小时）。

    Returns:
        解包后的检测结果。
    """
    return unwrap(get_analytics_tools().detect_viral_topics(threshold=threshold, time_window=time_window))


def keyword_cooccurrence(min_frequency: int = 2, top_n: int = 12) -> dict[str, Any]:
    """关键词共现分析（与 MCP analyze_keyword_cooccurrence 同源）。

    Args:
        min_frequency: 最小共现频次。
        top_n: 返回 Top N 关键词对。

    Returns:
        解包后的共现结果。
    """
    return unwrap(
        get_analytics_tools().analyze_keyword_cooccurrence(min_frequency=min_frequency, top_n=top_n)
    )
