from __future__ import annotations

import json
import logging
import sys
import threading
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

_handler_lock = threading.Lock()

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

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = format(span_context.trace_id, "032x")
            payload["span_id"] = format(span_context.span_id, "016x")

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
    __slots__ = ("_level", "_logger")

    def __init__(self, level: str = "INFO") -> None:
        self._level = level.upper()
        self._logger = logging.getLogger("app")
        with _handler_lock:
            self._logger.setLevel(self._level)
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

    @classmethod
    def get_request_id(cls) -> str | None:
        return request_context.get()

    @classmethod
    def bind_request_id(cls, request_id: str | None) -> Token[str | None]:
        """Set request id for the current context; pass the token to `reset_request_id` when done."""
        return request_context.set(request_id)

    @classmethod
    def reset_request_id(cls, token: Token[str | None]) -> None:
        request_context.reset(token)

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
