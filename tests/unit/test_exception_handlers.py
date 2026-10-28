from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException

from src.api.exception_handlers import register_errors
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.core.exceptions import AppError, ConflictError, DatabaseError, NotFoundError, ValidationError
from src.core.logger import AppLogger

_ERROR_KEYS = {"status", "code", "comment", "obj", "request_id"}


def _app_raising(exc: Exception) -> FastAPI:
    """Minimal FastAPI app that raises the given exception on GET /."""
    app = FastAPI()
    register_errors(app)

    @app.get("/")
    async def _raise() -> None:
        raise exc

    @app.get("/items/{item_id}")
    async def _item(item_id: int) -> int:
        return item_id

    return app


def _client(exc: Exception = RuntimeError("unused")) -> TestClient:
    return TestClient(_app_raising(exc), raise_server_exceptions=False)


# ── AppError: HTTP status codes ───────────────────────────────────────────────


def test_not_found_error_returns_404() -> None:
    assert _client(NotFoundError("User", "u-1")).get("/").status_code == 404


def test_conflict_error_returns_409() -> None:
    assert _client(ConflictError("already exists")).get("/").status_code == 409


def test_validation_error_returns_422() -> None:
    assert _client(ValidationError("bad input")).get("/").status_code == 422


def test_database_error_returns_500() -> None:
    assert _client(DatabaseError("db failure")).get("/").status_code == 500


# ── AppError: response body ───────────────────────────────────────────────────


def test_response_body_has_required_fields() -> None:
    body = _client(ConflictError("conflict msg")).get("/").json()
    assert set(body.keys()) == _ERROR_KEYS


def test_response_status_field_is_error() -> None:
    assert _client(ConflictError("x")).get("/").json()["status"] == "error"


def test_response_code_matches_exception_code() -> None:
    assert _client(NotFoundError("Order", "o-99")).get("/").json()["code"] == "NOT_FOUND"


def test_response_comment_matches_exception_message() -> None:
    assert _client(ConflictError("already exists")).get("/").json()["comment"] == "already exists"


def test_response_obj_is_null() -> None:
    assert _client(DatabaseError("boom")).get("/").json()["obj"] is None


@pytest.mark.parametrize(
    "exc",
    [
        DatabaseError("db"),
        ValidationError("val"),
        NotFoundError("Entity", "id-1"),
        ConflictError("conflict"),
    ],
)
def test_all_app_error_subclasses_are_handled(exc: AppError) -> None:
    response = _client(exc).get("/")
    assert response.status_code == exc.http_status_code
    assert response.json()["code"] == exc.code


# ── framework errors use the same format ──────────────────────────────────────


def test_request_validation_error_uses_unified_format() -> None:
    response = _client().get("/items/not-a-number")
    body = response.json()
    assert response.status_code == 422
    assert set(body.keys()) == _ERROR_KEYS
    assert body["code"] == "VALIDATION_ERROR"
    assert body["obj"][0]["loc"] == ["path", "item_id"]
    assert body["obj"][0]["type"] == "int_parsing"


def test_unknown_route_returns_unified_404() -> None:
    response = _client().get("/no-such-route")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_http_exception_keeps_status_and_headers() -> None:
    exc = HTTPException(status_code=503, detail="Postgres is unavailable", headers={"Retry-After": "5"})
    response = _client(exc).get("/")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json()["code"] == "HTTP_ERROR"
    assert response.json()["comment"] == "Postgres is unavailable"


def test_unexpected_exception_returns_json_500_without_internals() -> None:
    response = _client(RuntimeError("secret internals")).get("/")
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert "secret" not in body["comment"]


# ── request id ────────────────────────────────────────────────────────────────


def _client_with_request_id(exc: Exception) -> TestClient:
    app = _app_raising(exc)
    app.add_middleware(RequestLoggingMiddleware, logger=AppLogger(level="DEBUG"))
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("exc", [NotFoundError("User", "u-1"), RuntimeError("boom")])
def test_error_body_and_header_contain_request_id(exc: Exception) -> None:
    response = _client_with_request_id(exc).get("/", headers={"X-Request-ID": "req-42"})
    assert response.json()["request_id"] == "req-42"
    assert response.headers["x-request-id"] == "req-42"
