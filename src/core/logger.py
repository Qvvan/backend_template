from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """JSON formatter for application logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "logger": record.name,
        }

        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)

        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_value) if exc_value else None,
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(payload, ensure_ascii=False, default=str)


class AppLogger:
    __slots__ = ("level", "_logger")

    def __init__(self, level: str = "INFO") -> None:
        self.level = level.upper()
        self._logger = logging.getLogger("app")
        self._logger.setLevel(self.level)
        self._logger.propagate = False

        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonFormatter())
            self._logger.addHandler(handler)

    @classmethod
    def set_request_id(cls, request_id: str) -> None:
        request_context.set(request_id)

    @classmethod
    def clear_request_id(cls) -> None:
        request_context.set(None)

    @staticmethod
    def _extra(fields: dict[str, Any]) -> dict[str, Any]:
        return {"request_id": request_context.get(), "fields": fields}

    def debug(self, message: str, **fields: Any) -> None:
        self._logger.debug(message, extra=self._extra(fields))

    def info(self, message: str, **fields: Any) -> None:
        self._logger.info(message, extra=self._extra(fields))

    def warning(self, message: str, **fields: Any) -> None:
        self._logger.warning(message, extra=self._extra(fields))

    def error(self, message: str, **fields: Any) -> None:
        has_active_exception = sys.exc_info()[0] is not None
        self._logger.error(
            message,
            extra=self._extra(fields),
            exc_info=has_active_exception,
        )

    def critical(self, message: str, **fields: Any) -> None:
        self._logger.critical(message, extra=self._extra(fields))
