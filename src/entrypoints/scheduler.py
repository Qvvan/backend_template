from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.v1.workers import router as workers_router
from src.core.config import Config
from src.core.container import Container
from src.entrypoints.app_builder import build_app


def create_scheduler_app(config: Config | None = None, container: Container | None = None) -> FastAPI:
    """Background workers process + workers admin API (/api/v1/workers).

    Run exactly one instance (one granian worker, one replica): every instance would run every worker.
    """
    cfg = config or Config()
    app_container = container or Container(cfg)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        app_container.workers.start()
        yield
        await app_container.closer()

    return build_app(
        title="Scheduler",
        container=app_container,
        debug=cfg.app.DEBUG,
        lifespan=lifespan,
        routers=[workers_router],
    )
