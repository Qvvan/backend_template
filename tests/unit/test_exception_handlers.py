from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.exception_handlers import register_errors
from src.core.exceptions import AppError, ConflictError, DatabaseError, NotFoundError, ValidationError


def _app_raising(exc: AppError) -> FastAPI:
    """Minimal FastAPI app that raises the given exception on GET /."""
    app = FastAPI()
    register_errors(app)

    @app.get("/")
    async def _raise() -> None:
        raise exc

    return app


# ── HTTP status codes ─────────────────────────────────────────────────────────


def test_not_found_error_returns_404() -> None:
    client = TestClient(_app_raising(NotFoundError("User", "u-1")))
    response = client.get("/")
    assert response.status_code == 404


def test_conflict_error_returns_409() -> None:
    client = TestClient(_app_raising(ConflictError("already exists")))
    response = client.get("/")
    assert response.status_code == 409


def test_validation_error_returns_422() -> None:
    client = TestClient(_app_raising(ValidationError("bad input")))
    response = client.get("/")
    assert response.status_code == 422


def test_database_error_returns_500() -> None:
    client = TestClient(_app_raising(DatabaseError("db failure")))
    response = client.get("/")
    assert response.status_code == 500


# ── response body structure ───────────────────────────────────────────────────


def test_response_body_has_required_fields() -> None:
    client = TestClient(_app_raising(ConflictError("conflict msg")))
    body = client.get("/").json()
    assert set(body.keys()) == {"status", "code", "comment", "obj"}


def test_response_status_field_is_error() -> None:
    client = TestClient(_app_raising(ConflictError("x")))
    assert client.get("/").json()["status"] == "error"


def test_response_code_matches_exception_code() -> None:
    client = TestClient(_app_raising(NotFoundError("Order", "o-99")))
    assert client.get("/").json()["code"] == "NOT_FOUND"


def test_response_comment_matches_exception_message() -> None:
    client = TestClient(_app_raising(ConflictError("already exists")))
    assert client.get("/").json()["comment"] == "already exists"


def test_response_obj_is_null() -> None:
    client = TestClient(_app_raising(DatabaseError("boom")))
    assert client.get("/").json()["obj"] is None


# ── all subclasses produce a response, not a server crash ────────────────────


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
    client = TestClient(_app_raising(exc))
    response = client.get("/")
    assert response.status_code == exc.http_status_code
    assert response.json()["code"] == exc.code
