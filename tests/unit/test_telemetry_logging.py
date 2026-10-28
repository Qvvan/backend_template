from __future__ import annotations

import json
import logging

from opentelemetry.sdk.trace import TracerProvider

from src.core.logger import JsonFormatter


def _record() -> logging.LogRecord:
    return logging.LogRecord(name="app", level=logging.INFO, pathname="", lineno=0, msg="m", args=(), exc_info=None)


def test_log_has_no_trace_id_outside_a_span() -> None:
    payload = json.loads(JsonFormatter().format(_record()))
    assert "trace_id" not in payload


def test_log_contains_trace_and_span_id_inside_a_span() -> None:
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("op") as span:
        payload = json.loads(JsonFormatter().format(_record()))
        context = span.get_span_context()
    assert payload["trace_id"] == format(context.trace_id, "032x")
    assert payload["span_id"] == format(context.span_id, "016x")
