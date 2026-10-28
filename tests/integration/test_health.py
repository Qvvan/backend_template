from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_postgres_db, get_rabbitmq, get_redis
from src.api.exception_handlers import register_errors
from src.api.health import router
from src.interfaces.clients.cache_client.client import ICacheDB
from src.interfaces.clients.db.connection import IDBTransactional
from src.interfaces.messaging.rabbitmq.client import IAMQPClient


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    register_errors(application)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _postgres(healthy: bool) -> IDBTransactional:
    mock = AsyncMock(spec=IDBTransactional)
    mock.health_check.return_value = healthy
    return mock  # type: ignore[return-value]


def _rabbitmq(healthy: bool) -> IAMQPClient:
    mock = AsyncMock(spec=IAMQPClient)
    mock.health_check.return_value = healthy
    return mock  # type: ignore[return-value]


def _redis(healthy: bool) -> ICacheDB:
    mock = AsyncMock(spec=ICacheDB)
    mock.health_check.return_value = healthy
    return mock  # type: ignore[return-value]


def test_root_returns_ok(client: TestClient) -> None:
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_postgres_healthy(app: FastAPI, client: TestClient) -> None:
    app.dependency_overrides[get_postgres_db] = lambda: _postgres(True)
    response = client.get("/health/postgresql")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    app.dependency_overrides.clear()


def test_postgres_unavailable(app: FastAPI, client: TestClient) -> None:
    app.dependency_overrides[get_postgres_db] = lambda: _postgres(False)
    response = client.get("/health/postgresql")
    assert response.status_code == 503
    app.dependency_overrides.clear()


def test_rabbitmq_healthy(app: FastAPI, client: TestClient) -> None:
    app.dependency_overrides[get_rabbitmq] = lambda: _rabbitmq(True)
    response = client.get("/health/rabbitmq")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    app.dependency_overrides.clear()


def test_rabbitmq_unavailable(app: FastAPI, client: TestClient) -> None:
    app.dependency_overrides[get_rabbitmq] = lambda: _rabbitmq(False)
    response = client.get("/health/rabbitmq")
    assert response.status_code == 503
    app.dependency_overrides.clear()


def test_redis_healthy(app: FastAPI, client: TestClient) -> None:
    app.dependency_overrides[get_redis] = lambda: _redis(True)
    response = client.get("/health/redis")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    app.dependency_overrides.clear()


def test_redis_unavailable(app: FastAPI, client: TestClient) -> None:
    app.dependency_overrides[get_redis] = lambda: _redis(False)
    response = client.get("/health/redis")
    assert response.status_code == 503
    app.dependency_overrides.clear()
