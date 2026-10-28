from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import Config
from src.core.container import Container
from src.entrypoints.app_builder import build_app


def create_consumer_app(config: Config | None = None, container: Container | None = None) -> FastAPI:
    """Message consumer process: RabbitMQ/Kafka subscriptions + health probes and metrics over HTTP.

    Scale it horizontally: RabbitMQ consumers compete for messages, Kafka consumers share partitions.
    """
    cfg = config or Config()
    app_container = container or Container(cfg)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        await app_container.consumers.start()  # fails fast if a broker is unreachable
        yield
        await app_container.closer()

    return build_app(title="Consumer", container=app_container, debug=cfg.app.DEBUG, lifespan=lifespan)
