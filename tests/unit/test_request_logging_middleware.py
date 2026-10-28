from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.core.logger import AppLogger, request_context


@pytest.fixture
def app_logger() -> AppLogger:
    return AppLogger(level="DEBUG")


@pytest.fixture
def app(app_logger: AppLogger) -> FastAPI:
    application = FastAPI()
    application.add_middleware(RequestLoggingMiddleware, logger=app_logger, quiet_paths=frozenset({"/quiet"}))

    @application.get("/ok")
    async def ok(request: Request) -> dict[str, str | None]:
        return {"state": request.state.request_id, "context": AppLogger.get_request_id()}

    @application.get("/created", status_code=201)
    async def created() -> dict[str, str]:
        return {}

    @application.get("/quiet")
    async def quiet() -> dict[str, str]:
        return {}

    @application.get("/boom")
    async def boom() -> None:
        raise RuntimeError("simulated error")

    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def logged(app_logger: AppLogger) -> Iterator[list[str]]:
    """Messages written through AppLogger during the test (the 'app' logger does not propagate)."""
    handler = _ListHandler()
    app_logger_ = logging.getLogger("app")
    app_logger_.addHandler(handler)
    yield handler.messages
    app_logger_.removeHandler(handler)


# ── request id ────────────────────────────────────────────────────────────────


def test_response_contains_generated_uuid_request_id(client: TestClient) -> None:
    response = client.get("/ok")
    uuid.UUID(response.headers["x-request-id"])  # raises ValueError if not a valid UUID


def test_incoming_request_id_is_reused(client: TestClient) -> None:
    response = client.get("/ok", headers={"X-Request-ID": "gateway-123"})
    assert response.headers["x-request-id"] == "gateway-123"


def test_unsafe_incoming_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/ok", headers={"X-Request-ID": "bad id\nwith newline"})
    uuid.UUID(response.headers["x-request-id"])


def test_too_long_incoming_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/ok", headers={"X-Request-ID": "a" * 129})
    uuid.UUID(response.headers["x-request-id"])


def test_request_id_available_in_state_and_logger_context(client: TestClient) -> None:
    response = client.get("/ok", headers={"X-Request-ID": "req-1"})
    assert response.json() == {"state": "req-1", "context": "req-1"}


def test_each_request_gets_unique_request_id(client: TestClient) -> None:
    first = client.get("/ok").headers["x-request-id"]
    second = client.get("/ok").headers["x-request-id"]
    assert first != second


def test_request_id_context_is_reset_after_request(client: TestClient) -> None:
    client.get("/ok")
    assert request_context.get() is None


def test_original_response_status_is_preserved(client: TestClient) -> None:
    assert client.get("/created").status_code == 201


# ── logging ───────────────────────────────────────────────────────────────────


def test_request_and_response_are_logged(client: TestClient, logged: list[str]) -> None:
    client.get("/ok")
    assert logged == ["Incoming request", "Outgoing response"]


def test_quiet_paths_are_not_logged(client: TestClient, logged: list[str]) -> None:
    response = client.get("/quiet")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert logged == []


# ── error path ────────────────────────────────────────────────────────────────


def test_exception_propagates_and_is_logged(app: FastAPI, logged: list[str]) -> None:
    with pytest.raises(RuntimeError, match="simulated error"):
        TestClient(app).get("/boom")
    assert "Request failed" in logged
    assert request_context.get() is None
