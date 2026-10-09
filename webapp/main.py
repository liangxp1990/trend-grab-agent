"""FastAPI 应用入口。

启动：uvicorn webapp.main:app --host 0.0.0.0 --port 8080

生命周期：建库 → 幂等初始化（admin/配置 v1/版本快照）→ 启动内置调度器。
静态资源：/reports 托管引擎 HTML 报告；/ 托管前端构建产物（frontend/dist）。
实时性说明：M1 采用前端轮询（任务状态/日志），WebSocket 推送在 M2 引入。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import events
from .config import SETTINGS
from .database import init_db
from .routers import auth, config_api, data_api, jobs, reports, system
from .scheduler import start_scheduler
from .security import decode_access_token
from .seed import run_seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：初始化数据库与种子数据，启动调度器与事件循环注册。"""
    events.set_loop(asyncio.get_running_loop())
    init_db()
    run_seed()
    start_scheduler()
    yield


def create_app() -> FastAPI:
    """构建 FastAPI 应用（注册路由、静态资源与中间件）。

    Returns:
        配置完成的 FastAPI 实例。
    """
    app = FastAPI(title="TrendRadar 管理平台", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (auth.router, config_api.router, jobs.router, data_api.router, reports.router, system.router):
        app.include_router(router)

    @app.get("/api/v1/health", tags=["system"])
    async def health() -> dict[str, str]:
        """健康检查（无鉴权，供容器探针；须先于 SPA fallback 注册）。"""
        return {"status": "ok"}

    @app.websocket("/api/v1/ws/status")
    async def ws_status(websocket: WebSocket) -> None:
        """实时状态 WebSocket：推送任务状态与日志流（token 查询参数鉴权）。"""
        try:
            decode_access_token(websocket.query_params.get("token", ""))
        except Exception:  # noqa: BLE001 令牌无效统一拒绝
            await websocket.close(code=4401)
            return
        await websocket.accept()
        queue = events.subscribe()
        try:
            while True:
                message = await queue.get()
                await websocket.send_text(message)
        except WebSocketDisconnect:
            pass
        finally:
            events.unsubscribe(queue)

    reports_root = SETTINGS.output_dir / "html"
    reports_root.mkdir(parents=True, exist_ok=True)
    app.mount("/reports", StaticFiles(directory=str(reports_root)), name="reports")

    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

        @app.get("/", include_in_schema=False)
        async def spa_root() -> FileResponse:
            """SPA 入口。"""
            return FileResponse(dist / "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            """SPA 路由回退（非 API/静态路径返回 index.html）。"""
            candidate = dist / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
