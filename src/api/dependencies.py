from fastapi import Request

from src.core.container import Container
from src.interfaces.clients.cache_client.client import ICacheDB
from src.interfaces.clients.db.connection import IDBTransactional

from src.interfaces.messaging.client import IAMQPClient


def get_container(request: Request) -> Container:
    return request.app.state.container

def get_postgres_db(request: Request) -> IDBTransactional:
    return request.app.state.container.infra.postgres_db

def get_rabbitmq(request: Request) -> IAMQPClient:
    return request.app.state.container.infra.rabbitmq

def get_redis(request: Request) -> ICacheDB:
    return request.app.state.container.infra.redis_db
