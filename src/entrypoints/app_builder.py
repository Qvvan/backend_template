from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager

from fastapi import APIRouter, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.cors import CORSMiddleware

from src.api.exception_handlers import register_errors
from src.api.health import router as health_router
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.core.container import Container

METRICS_PATH = "/metrics"
# Probes and metrics are scraped every few seconds: keep them out of request logs and metrics
QUIET_PATHS = frozenset({METRICS_PATH, "/livez", "/readyz"})


def build_app(
    *,
    title: str,
    container: Container,
    debug: bool,
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]],
    routers: Sequence[APIRouter] = (),
    cors_origins: Sequence[str] = (),
) -> FastAPI:
    """FastAPI app with everything every process needs: errors, request id, logging, health, metrics."""
    app = FastAPI(
        title=title,
        lifespan=lifespan,
        docs_url="/docs" if debug else None,
        redoc_url="/redoc" if debug else None,
        openapi_url="/openapi.json" if debug else None,
    )
    app.state.container = container

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,  # type: ignore[arg-type]  # Starlette's middleware typing is stricter than the classes
            allow_origins=list(cors_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(
        RequestLoggingMiddleware,  # type: ignore[arg-type]  # Starlette's middleware typing rejects plain ASGI classes
        logger=container.logger,
        quiet_paths=QUIET_PATHS,
    )
    register_errors(app)

    app.include_router(health_router)
    for router in routers:
        app.include_router(router)

    Instrumentator(excluded_handlers=list(QUIET_PATHS)).instrument(app).expose(
        app, endpoint=METRICS_PATH, include_in_schema=False
    )
    return app
