from __future__ import annotations

import json
import logging
import sys

from src.core.logger import AppLogger, JsonFormatter, request_context


def _make_record(msg: str = "test", level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_formatter_produces_valid_json() -> None:
    record = _make_record("hello world")
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["message"] == "hello world"
    assert parsed["level"] == "INFO"
    assert "timestamp" in parsed
    assert "logger" in parsed


def test_formatter_request_id_none_by_default() -> None:
    record = _make_record()
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["request_id"] is None


def test_formatter_includes_request_id_from_record() -> None:
    record = _make_record()
    record.__dict__["request_id"] = "req-xyz"
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["request_id"] == "req-xyz"


def test_formatter_includes_extra_fields() -> None:
    record = _make_record()
    record.__dict__["fields"] = {"user_id": "u-1", "status": "ok"}
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["user_id"] == "u-1"
    assert parsed["status"] == "ok"


def test_formatter_includes_exception_info() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = _make_record()
    record.exc_info = exc_info
    parsed = json.loads(JsonFormatter().format(record))
    assert "exception" in parsed
    assert parsed["exception"]["type"] == "ValueError"
    assert "boom" in parsed["exception"]["message"]
    assert parsed["exception"]["traceback"] is not None


def test_request_context_set_and_clear() -> None:
    AppLogger.set_request_id("req-abc")
    assert request_context.get() == "req-abc"
    AppLogger.clear_request_id()
    assert request_context.get() is None


def test_extra_propagates_context_and_fields() -> None:
    AppLogger.set_request_id("req-test")
    extra = AppLogger._extra({"action": "login", "user": "alice"})
    assert extra["request_id"] == "req-test"
    assert extra["fields"]["action"] == "login"
    assert extra["fields"]["user"] == "alice"
    AppLogger.clear_request_id()


def test_extra_request_id_none_when_not_set() -> None:
    AppLogger.clear_request_id()
    extra = AppLogger._extra({})
    assert extra["request_id"] is None
