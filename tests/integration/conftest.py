from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.rabbitmq import RabbitMqContainer
from testcontainers.redis import RedisContainer

from src.core.logger import AppLogger
from src.infrastructure.messaging.rabbitmq.client import RabbitMQClient
from src.infrastructure.repository.postgresql.client.connection import PostgresConnectionPool
from src.infrastructure.repository.postgresql.client.query_executor import PostgresQueryExecutor
from src.infrastructure.repository.redis.client import RedisDB
from src.infrastructure.repository.redis.repository import RedisRepository
from src.infrastructure.uow.postgres_uow import PostgresUnitOfWork


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16.2") as container:
        yield container


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7") as container:
        yield container


@pytest.fixture(scope="session")
def rabbit_container():
    with RabbitMqContainer("rabbitmq:3.13-management") as container:
        yield container


@pytest.fixture
def logger() -> AppLogger:
    return AppLogger(level="DEBUG")


@pytest.fixture
async def pg_pool(pg_container: PostgresContainer, logger: AppLogger) -> AsyncGenerator[PostgresConnectionPool, None]:
    pool = PostgresConnectionPool(
        logger=logger,
        host="localhost",
        port=int(pg_container.get_exposed_port(5432)),
        database=pg_container.dbname,
        user=pg_container.username,
        password=pg_container.password,
        pool_size=2,
    )
    yield pool
    await pool.close()


@pytest.fixture
def pg_executor(pg_pool: PostgresConnectionPool) -> PostgresQueryExecutor:
    return PostgresQueryExecutor(pg_pool)


@pytest.fixture
def pg_uow(pg_pool: PostgresConnectionPool) -> PostgresUnitOfWork:
    return PostgresUnitOfWork(pg_pool)


@pytest.fixture
async def redis_db(redis_container: RedisContainer, logger: AppLogger) -> AsyncGenerator[RedisDB, None]:
    db = RedisDB(
        logger=logger,
        host="localhost",
        port=int(redis_container.get_exposed_port(6379)),
        db=0,
    )
    yield db
    await db.close()


@pytest.fixture
def redis_repo(redis_db: RedisDB) -> RedisRepository:
    return RedisRepository(redis_db.client)


@pytest.fixture
async def rabbit_client(
    rabbit_container: RabbitMqContainer, logger: AppLogger
) -> AsyncGenerator[RabbitMQClient, None]:
    client = RabbitMQClient(
        logger=logger,
        host="localhost",
        port=int(rabbit_container.get_exposed_port(5672)),
        user=rabbit_container.username,
        password=rabbit_container.password,
        vhost="/",
        tls_enabled=False,
    )
    await client.connect()
    yield client
    await client.close()
