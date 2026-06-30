from __future__ import annotations

from fastapi import Request

from src.core.container import Container
from src.interfaces.clients.cache_client.client import ICacheDB
from src.interfaces.clients.db.connection import IDBTransactional
from src.interfaces.clients.storage.client import IStorageClient
from src.interfaces.messaging.client import IAMQPClient
from src.interfaces.workers.scheduler import IScheduler


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_postgres_db(request: Request) -> IDBTransactional:
    return request.app.state.container.infra.postgres_db


def get_rabbitmq(request: Request) -> IAMQPClient:
    return request.app.state.container.infra.rabbitmq


def get_redis(request: Request) -> ICacheDB:
    return request.app.state.container.infra.redis_db


def get_minio(request: Request) -> IStorageClient:
    return request.app.state.container.infra.minio_client


def get_scheduler(request: Request) -> IScheduler:
    return request.app.state.container.workers.scheduler
