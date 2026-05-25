from __future__ import annotations

from starlette import status

from src.core.exceptions import AppError, ConflictError, DatabaseError, NotFoundError, ValidationError


def test_app_error_defaults() -> None:
    err = AppError("something went wrong")
    assert err.message == "something went wrong"
    assert err.code == "UNKNOWN_ERROR"
    assert err.http_status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert str(err) == "something went wrong"


def test_app_error_custom_code() -> None:
    err = AppError("custom", code="CUSTOM_CODE")
    assert err.code == "CUSTOM_CODE"


def test_database_error() -> None:
    err = DatabaseError("db failed")
    assert err.code == "DATABASE_ERROR"
    assert err.http_status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert err.message == "db failed"


def test_validation_error() -> None:
    err = ValidationError("invalid input")
    assert err.code == "VALIDATION_ERROR"
    assert err.http_status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_not_found_error_message_format() -> None:
    err = NotFoundError("User", "user-123")
    assert err.code == "NOT_FOUND"
    assert err.http_status_code == status.HTTP_404_NOT_FOUND
    assert "User" in err.message
    assert "user-123" in err.message


def test_conflict_error() -> None:
    err = ConflictError("already exists")
    assert err.code == "CONFLICT"
    assert err.http_status_code == status.HTTP_409_CONFLICT


def test_all_domain_errors_inherit_from_app_error() -> None:
    for exc_cls in (DatabaseError, ValidationError, NotFoundError, ConflictError):
        assert issubclass(exc_cls, AppError), f"{exc_cls.__name__} must inherit from AppError"


def test_exceptions_are_catchable_as_app_error() -> None:
    for err in (
        DatabaseError("x"),
        ValidationError("x"),
        NotFoundError("X", "1"),
        ConflictError("x"),
    ):
        assert isinstance(err, AppError)
        assert isinstance(err, Exception)
