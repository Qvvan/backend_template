from __future__ import annotations

from enum import StrEnum

from starlette import status


class ErrorCode(StrEnum):
    """Machine-readable error codes returned in the `code` field of error responses."""

    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HTTP_ERROR = "HTTP_ERROR"


class AppError(Exception):
    """Базовое исключение приложения"""

    http_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str, code: str = ErrorCode.UNKNOWN_ERROR) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class DatabaseError(AppError):
    """Исключения при работе с БД"""

    http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message, ErrorCode.DATABASE_ERROR)


class ValidationError(AppError):
    """Исключения валидации"""

    http_status_code = status.HTTP_422_UNPROCESSABLE_CONTENT

    def __init__(self, message: str) -> None:
        super().__init__(message, ErrorCode.VALIDATION_ERROR)


class NotFoundError(AppError):
    """Сущность не найдена"""

    http_status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, entity: str, identifier: str) -> None:
        message = f"{entity} with identifier '{identifier}' not found"
        super().__init__(message, ErrorCode.NOT_FOUND)


class ConflictError(AppError):
    """Конфликт данных"""

    http_status_code = status.HTTP_409_CONFLICT

    def __init__(self, message: str) -> None:
        super().__init__(message, ErrorCode.CONFLICT)
