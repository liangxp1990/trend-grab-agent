"""进程内事件总线：runner 线程 → WebSocket 连接的实时广播。

runner 在后台线程执行，WebSocket 在事件循环中等待——桥接方式：
主循环引用 + loop.call_soon_threadsafe 投递，保证线程安全。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("webapp.events")

_subscribers: list[asyncio.Queue] = []
_main_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    """注册主事件循环（应用启动时调用一次）。

    Args:
        loop: FastAPI 所在 asyncio 事件循环。
    """
    global _main_loop
    _main_loop = loop


def subscribe() -> asyncio.Queue:
    """新建一个订阅队列（每个 WebSocket 连接一个）。

    Returns:
        绑定到主循环的队列。
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    _subscribers.append(queue)
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    """注销订阅（连接断开时调用）。

    Args:
        queue: subscribe() 返回的队列。
    """
    if queue in _subscribers:
        _subscribers.remove(queue)


def broadcast(payload: dict[str, Any]) -> None:
    """向全部订阅者广播事件（线程安全，可从 runner 线程调用）。

    消费缓慢（队列满）时丢弃该连接的本条消息，不影响其他连接。

    Args:
        payload: 事件负载（如 {"type": "log", "job_id": 1, "text": "..."}）。
    """
    if _main_loop is None:
        return
    message = json.dumps(payload, ensure_ascii=False)

    def _deliver() -> None:
        dropped: list[asyncio.Queue] = []
        for queue in _subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                dropped.append(queue)
        for queue in dropped:
            logger.warning("订阅者消费过慢，丢弃消息")

    try:
        _main_loop.call_soon_threadsafe(_deliver)
    except RuntimeError:
        pass  # 循环已关闭（停机中）
