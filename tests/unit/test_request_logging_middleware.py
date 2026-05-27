from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.core.logger import AppLogger, request_context


@pytest.fixture
def app_logger() -> AppLogger:
    return AppLogger(level="DEBUG")


@pytest.fixture
def middleware(app_logger: AppLogger) -> RequestLoggingMiddleware:
    return RequestLoggingMiddleware(app=MagicMock(), logger=app_logger)


def _make_request(method: str = "GET", path: str = "/test") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "scheme": "http",
        "server": ("testserver", 80),
        "root_path": "",
        "path": path,
        "query_string": b"",
        "headers": [],
    }
    return Request(scope)


def _ok_call_next(status_code: int = 200) -> Callable[[Request], Awaitable[Response]]:
    async def _call_next(_request: Request) -> Response:
        return Response(content=b"ok", status_code=status_code)

    return _call_next


# ── happy path ────────────────────────────────────────────────────────────────


async def test_response_contains_x_request_id_header(middleware: RequestLoggingMiddleware) -> None:
    response = await middleware.dispatch(_make_request(), _ok_call_next())
    assert "x-request-id" in response.headers


async def test_x_request_id_is_valid_uuid(middleware: RequestLoggingMiddleware) -> None:
    response = await middleware.dispatch(_make_request(), _ok_call_next())
    # raises ValueError if not a valid UUID
    uuid.UUID(response.headers["x-request-id"])


async def test_request_state_receives_request_id(middleware: RequestLoggingMiddleware) -> None:
    request = _make_request()
    await middleware.dispatch(request, _ok_call_next())
    # state is set during dispatch; value is a valid UUID string
    uuid.UUID(request.state.request_id)


async def test_request_id_cleared_from_context_after_success(
    middleware: RequestLoggingMiddleware,
) -> None:
    AppLogger.set_request_id("pre-existing")
    await middleware.dispatch(_make_request(), _ok_call_next())
    assert request_context.get() is None


async def test_each_request_gets_unique_request_id(middleware: RequestLoggingMiddleware) -> None:
    r1 = await middleware.dispatch(_make_request(), _ok_call_next())
    r2 = await middleware.dispatch(_make_request(), _ok_call_next())
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


async def test_original_response_status_is_preserved(middleware: RequestLoggingMiddleware) -> None:
    response = await middleware.dispatch(_make_request(), _ok_call_next(status_code=201))
    assert response.status_code == 201


# ── error path ────────────────────────────────────────────────────────────────


async def test_exception_propagates_from_dispatch(middleware: RequestLoggingMiddleware) -> None:
    async def _failing(_request: Request) -> Response:
        raise RuntimeError("simulated error")

    with pytest.raises(RuntimeError, match="simulated error"):
        await middleware.dispatch(_make_request(), _failing)


async def test_request_id_cleared_after_exception(middleware: RequestLoggingMiddleware) -> None:
    async def _failing(_request: Request) -> Response:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await middleware.dispatch(_make_request(), _failing)

    assert request_context.get() is None
