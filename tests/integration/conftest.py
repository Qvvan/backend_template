from __future__ import annotations

import socket
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs
from testcontainers.postgres import PostgresContainer
from testcontainers.rabbitmq import RabbitMqContainer
from testcontainers.redis import RedisContainer
from yoyo import get_backend, read_migrations

from src.core.logger import AppLogger
from src.infrastructure.messaging.kafka.client import KafkaClient
from src.infrastructure.messaging.rabbitmq.client import RabbitMQClient
from src.infrastructure.repository.postgresql.client.connection import PostgresConnectionPool
from src.infrastructure.repository.postgresql.client.query_executor import PostgresQueryExecutor
from src.infrastructure.repository.postgresql.client.transaction_executor import PostgresTransactionExecutor
from src.infrastructure.repository.redis.client import RedisDB
from src.infrastructure.repository.redis.repository import RedisRepository
from src.infrastructure.uow.postgres_uow import PostgresUnitOfWork

# Keep in sync with docker-compose.yml
POSTGRES_IMAGE = "postgres:16.2"
REDIS_IMAGE = "redis:7"
RABBITMQ_IMAGE = "rabbitmq:3.13-management"
KAFKA_IMAGE = "apache/kafka:4.3.1"

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
MIGRATION_TABLE = "_yoyo_migration"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("localhost", 0))
        return sock.getsockname()[1]


@pytest.fixture
def logger() -> AppLogger:
    return AppLogger(level="DEBUG")


# ── PostgreSQL ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def pg_container() -> Iterator[PostgresContainer]:
    """Postgres with all yoyo migrations from migrations/ applied — the same schema as production."""
    with PostgresContainer(POSTGRES_IMAGE) as container:
        url = (
            f"postgresql://{container.username}:{container.password}"
            f"@localhost:{container.get_exposed_port(5432)}/{container.dbname}"
        )
        backend = get_backend(url, migration_table=MIGRATION_TABLE)
        with backend.lock():
            backend.apply_migrations(backend.to_apply(read_migrations(str(MIGRATIONS_DIR))))
        yield container


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
async def db_executor(pg_pool: PostgresConnectionPool) -> AsyncGenerator[PostgresTransactionExecutor, None]:
    """Executor inside a transaction that is rolled back after the test: repositories tests stay isolated."""
    async with pg_pool.get_connection() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            yield PostgresTransactionExecutor(conn)
        finally:
            await tx.rollback()


# ── Redis ─────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def redis_container() -> Iterator[RedisContainer]:
    with RedisContainer(REDIS_IMAGE) as container:
        yield container


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


# ── RabbitMQ ──────────────────────────────────────────────────────────────────

RABBIT_RETRY_DELAYS = (0.1, 0.1)


@pytest.fixture(scope="session")
def rabbit_container() -> Iterator[RabbitMqContainer]:
    with RabbitMqContainer(RABBITMQ_IMAGE) as container:
        yield container


@pytest.fixture
async def rabbit_client(rabbit_container: RabbitMqContainer, logger: AppLogger) -> AsyncGenerator[RabbitMQClient, None]:
    client = RabbitMQClient(
        logger=logger,
        host="localhost",
        port=int(rabbit_container.get_exposed_port(5672)),
        user=rabbit_container.username,
        password=rabbit_container.password,
        vhost="/",
        tls_enabled=False,
        retry_delays=RABBIT_RETRY_DELAYS,
    )
    await client.connect()
    yield client
    await client.close()


# ── Kafka ─────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def kafka_bootstrap() -> Iterator[str]:
    """Single-node KRaft Kafka; the host port is fixed so the advertised listener is reachable."""
    port = _free_port()
    container = (
        DockerContainer(KAFKA_IMAGE)
        .with_bind_ports(9092, port)
        .with_env("KAFKA_NODE_ID", "1")
        .with_env("KAFKA_PROCESS_ROLES", "broker,controller")
        .with_env("KAFKA_LISTENERS", "PLAINTEXT://:9092,CONTROLLER://:9093")
        .with_env("KAFKA_ADVERTISED_LISTENERS", f"PLAINTEXT://localhost:{port}")
        .with_env("KAFKA_LISTENER_SECURITY_PROTOCOL_MAP", "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT")
        .with_env("KAFKA_CONTROLLER_LISTENER_NAMES", "CONTROLLER")
        .with_env("KAFKA_CONTROLLER_QUORUM_VOTERS", "1@localhost:9093")
        .with_env("KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR", "1")
        .with_env("KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR", "1")
        .with_env("KAFKA_TRANSACTION_STATE_LOG_MIN_ISR", "1")
        .with_env("KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS", "0")
    )
    with container:
        wait_for_logs(container, "Kafka Server started", timeout=90)
        yield f"localhost:{port}"


@pytest.fixture
async def kafka_client(kafka_bootstrap: str, logger: AppLogger) -> AsyncGenerator[KafkaClient, None]:
    client = KafkaClient(
        logger=logger,
        bootstrap_servers=kafka_bootstrap,
        client_id="tests",
        auto_offset_reset="earliest",
        max_retries=2,
        retry_backoff=0.05,
    )
    yield client
    await client.close()
