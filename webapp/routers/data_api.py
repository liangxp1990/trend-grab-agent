"""数据查询路由：只读访问引擎日库（output/news/{date}.db）。

遵循 D5 决策：日库引擎独占写、平台只读，因此以 mode=ro 打开，
不存在时返回空集而非报错（未运行任务的日期属正常情况）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Query

from ..config import SETTINGS
from ..schemas import NewsItem, NewsPage
from ..security import CurrentUser

router = APIRouter(prefix="/api/v1/data", tags=["data"])

_PAGE_SIZE_CAP = 100


def _connect_ro(db_path: Path) -> sqlite3.Connection | None:
    """以只读模式打开日库。

    Args:
        db_path: SQLite 文件路径。

    Returns:
        连接；文件不存在返回 None。
    """
    if not db_path.is_file():
        return None
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


@router.get("/news", response_model=NewsPage)
def query_news(
    current: CurrentUser,
    date: str = Query(default="", description="YYYY-MM-DD，默认今天"),
    platform: str = Query(default="", description="平台 id 过滤"),
    q: str = Query(default="", max_length=64, description="标题关键词"),
    limit: int = Query(default=50, ge=1, le=_PAGE_SIZE_CAP),
    offset: int = Query(default=0, ge=0),
) -> NewsPage:
    """按日期查询热榜条目（标题模糊匹配 + 平台过滤 + 分页）。"""
    from datetime import datetime

    target = date or datetime.now().strftime("%Y-%m-%d")
    conn = _connect_ro(SETTINGS.output_dir / "news" / f"{target}.db")
    if conn is None:
        return NewsPage(total=0, items=[])
    try:
        conn.row_factory = sqlite3.Row
        conditions: list[str] = []
        params: list[str | int] = []
        if platform:
            conditions.append("p.id = ?")
            params.append(platform)
        if q:
            conditions.append("n.title LIKE ?")
            params.append(f"%{q}%")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        total = conn.execute(
            f"SELECT COUNT(*) FROM news_items n JOIN platforms p ON n.platform_id = p.id {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT n.id, n.title, p.name AS platform, n.rank, n.crawl_count,
                   n.first_crawl_time, n.last_crawl_time, n.url
            FROM news_items n JOIN platforms p ON n.platform_id = p.id
            {where}
            ORDER BY n.rank ASC, n.crawl_count DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        items = [
            NewsItem(
                id=row["id"],
                title=row["title"],
                platform=row["platform"],
                rank=row["rank"] or 0,
                crawl_count=row["crawl_count"] or 0,
                first_crawl_time=row["first_crawl_time"],
                last_crawl_time=row["last_crawl_time"],
                url=row["url"] or "",
            )
            for row in rows
        ]
        return NewsPage(total=total, items=items)
    finally:
        conn.close()


@router.get("/dates")
def available_dates(current: CurrentUser) -> dict:
    """列出本地有数据的天数（报告与查询的日期选择器数据源）。"""
    news_dir = SETTINGS.output_dir / "news"
    dates = sorted(
        (p.stem for p in news_dir.glob("*.db") if len(p.stem) == 10),
        reverse=True,
    )
    return {"dates": dates[:90]}


def _recent_dbs(days: int) -> list[tuple[str, Path]]:
    """返回最近 N 天存在的日库 [(date, path)]，旧→新。"""
    from datetime import datetime, timedelta

    news_dir = SETTINGS.output_dir / "news"
    today = datetime.now().date()
    result = []
    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        path = news_dir / f"{day}.db"
        if path.is_file():
            result.append((day, path))
    return result


@router.get("/platforms/health")
def platforms_health(current: CurrentUser, days: int = Query(default=7, ge=1, le=30)) -> dict:
    """各数据源近 N 天抓取成功率热力（读 crawl_source_status 聚合）。

    Returns:
        {"days": [日期], "platforms": [{"id", "name", "values": [rate|None]}]}。
    """
    dbs = _recent_dbs(days)
    platform_names: dict[str, str] = {}
    per_platform: dict[str, list[float | None]] = {}
    for idx, (_day, path) in enumerate(dbs):
        conn = _connect_ro(path)
        if conn is None:
            continue
        try:
            rows = conn.execute(
                """
                SELECT p.id, p.name,
                       SUM(CASE WHEN cs.status='success' THEN 1 ELSE 0 END) AS ok,
                       COUNT(*) AS total
                FROM crawl_source_status cs JOIN platforms p ON cs.platform_id = p.id
                GROUP BY p.id
                """
            ).fetchall()
            for pid, name, ok, total in rows:
                platform_names[pid] = name
                per_platform.setdefault(pid, [None] * len(dbs))[idx] = (ok / total) if total else None
        finally:
            conn.close()
    return {
        "days": [d for d, _ in dbs],
        "platforms": [
            {"id": pid, "name": platform_names.get(pid, pid), "values": per_platform[pid]}
            for pid in sorted(platform_names)
        ],
    }


def _load_word_groups() -> list[tuple[str, list[str]]]:
    """解析共享卷词表 [WORD_GROUPS] 段，产出 (别名, 匹配词列表)。

    支持引擎两种行格式：
    - ``/词a|词b|\\bWord\\b/ => 别名``（正则词组，取别名显示、拆词匹配）
    - ``词a, 词b`` 或单词（无别名，首个词即显示名）
    [GLOBAL_FILTER] 段与其余段跳过。
    """
    words_file = SETTINGS.config_dir / "frequency_words.txt"
    if not words_file.is_file():
        return []
    groups: list[tuple[str, list[str]]] = []
    in_groups = False
    for raw in words_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_groups = "WORD_GROUPS" in line
            continue
        if not in_groups:
            continue
        alias = ""
        if "=>" in line:
            left, alias = line.split("=>", 1)
            alias = alias.strip()
        else:
            left = line
        left = left.split("@")[0].strip()
        if left.startswith("/"):
            left = left.strip("/")
        terms = [t.strip() for t in left.split("|") if t.strip()]
        terms = [t.replace("\\b", "") for t in terms]
        terms = [t for t in terms if len(t) >= 2 or t.isascii() and len(t) >= 2]
        if not terms:
            continue
        name = alias or terms[0]
        groups.append((name, terms))
    return groups[:16]


@router.get("/trends/keywords")
def trends_keywords(current: CurrentUser, days: int = Query(default=7, ge=1, le=14)) -> dict:
    """词表关键词组近 N 天每日命中条数（标题含任一匹配词即计 1，近似引擎口径）。

    Returns:
        {"days": [日期], "keywords": [{"word", "values": [count]}]}。
    """
    dbs = _recent_dbs(days)
    groups = _load_word_groups()
    counters: dict[str, list[int]] = {name: [0] * len(dbs) for name, _ in groups}
    for idx, (_day, path) in enumerate(dbs):
        conn = _connect_ro(path)
        if conn is None:
            continue
        try:
            titles = [r[0] or "" for r in conn.execute("SELECT title FROM news_items").fetchall()]
        finally:
            conn.close()
        for name, terms in groups:
            counters[name][idx] = sum(1 for t in titles if any(w in t for w in terms))
    ranked = sorted(counters.items(), key=lambda kv: sum(kv[1]), reverse=True)[:12]
    return {
        "days": [d for d, _ in dbs],
        "keywords": [{"word": w, "values": v} for w, v in ranked],
    }


@router.get("/trends/platforms")
def trends_platforms(current: CurrentUser, days: int = Query(default=7, ge=1, le=14)) -> dict:
    """各平台近 N 天每日入库条数对比。

    Returns:
        {"days": [日期], "platforms": [{"id", "name", "values": [count]}]}。
    """
    dbs = _recent_dbs(days)
    names: dict[str, str] = {}
    counts: dict[str, list[int]] = {}
    for idx, (_day, path) in enumerate(dbs):
        conn = _connect_ro(path)
        if conn is None:
            continue
        try:
            for pid, name, cnt in conn.execute(
                "SELECT p.id, p.name, COUNT(n.id) FROM news_items n "
                "JOIN platforms p ON n.platform_id = p.id GROUP BY p.id"
            ).fetchall():
                names[pid] = name
                counts.setdefault(pid, [0] * len(dbs))[idx] = cnt
        finally:
            conn.close()
    ranked = sorted(counts.items(), key=lambda kv: sum(kv[1]), reverse=True)
    return {
        "days": [d for d, _ in dbs],
        "platforms": [{"id": pid, "name": names.get(pid, pid), "values": vals} for pid, vals in ranked],
    }


@router.get("/trends/viral")
def trends_viral(
    current: CurrentUser,
    threshold: float = Query(default=3.0, ge=1.5, le=20),
    time_window: int = Query(default=24, ge=6, le=168),
) -> dict:
    """异常爆火话题检测（复用 MCP AnalyticsTools，同源口径）。

    Returns:
        {"ok", "summary", "data", "message"}。
    """
    from .. import analytics as analytics_core

    return analytics_core.viral_topics(threshold=threshold, time_window=time_window)


@router.get("/trends/cooccurrence")
def trends_cooccurrence(
    current: CurrentUser,
    min_frequency: int = Query(default=2, ge=2, le=50),
    top_n: int = Query(default=12, ge=1, le=50),
) -> dict:
    """关键词共现分析（复用 MCP AnalyticsTools，同源口径）。

    Returns:
        {"ok", "summary", "data", "message"}。
    """
    from .. import analytics as analytics_core

    return analytics_core.keyword_cooccurrence(min_frequency=min_frequency, top_n=top_n)
