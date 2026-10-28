from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api import router
from src.core.config import Config
from src.core.container import Container
from src.core.telemetry import shutdown_tracing
from src.entrypoints.app_builder import build_app


def create_app(config: Config | None = None, container: Container | None = None) -> FastAPI:
    """HTTP API process. Background workers and consumers run in their own processes (src/entrypoints/)."""
    cfg = config or Config()
    app_container = container or Container(cfg)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        yield
        await app_container.closer()
        shutdown_tracing()

    return build_app(
        title="API",
        container=app_container,
        debug=cfg.app.DEBUG,
        telemetry=cfg.telemetry,
        lifespan=lifespan,
        routers=[router],
        cors_origins=cfg.app.CORS_ORIGINS,
    )
