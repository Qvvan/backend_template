from __future__ import annotations

import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.logger import AppLogger

REQUEST_ID_HEADER = "X-Request-ID"

_REQUEST_ID_HEADER_KEY = REQUEST_ID_HEADER.lower().encode("latin-1")
# Accept ids from upstream (gateway, other services) only if they are safe to put into logs.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope["headers"]:
        if name == _REQUEST_ID_HEADER_KEY:
            candidate = value.decode("latin-1")
            return candidate if _VALID_REQUEST_ID.match(candidate) else None
    return None


class RequestLoggingMiddleware:
    """Pure ASGI middleware: request id propagation and request/response logging.

    - Reuses a valid incoming `X-Request-ID` header or generates a new UUID.
    - Stores it in `request.state.request_id` and in the logger context.
    - Adds `X-Request-ID` to every response.
    - Paths from `quiet_paths` (probes, metrics) are not logged.
    """

    __slots__ = ("_app", "_logger", "_quiet_paths")

    def __init__(self, app: ASGIApp, logger: AppLogger, quiet_paths: frozenset[str] = frozenset()) -> None:
        self._app = app
        self._logger = logger
        self._quiet_paths = quiet_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = AppLogger.bind_request_id(request_id)

        method: str = scope["method"]
        path: str = scope["path"]
        quiet = path in self._quiet_paths
        status_code = 500
        start_time = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        if not quiet:
            self._logger.info("Incoming request", type="request", method=method, path=path)

        try:
            await self._app(scope, receive, send_with_request_id)
        except Exception as exc:
            self._logger.error(
                "Request failed",
                type="response",
                method=method,
                path=path,
                duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
                error_type=type(exc).__name__,
            )
            raise
        else:
            if not quiet:
                self._logger.info(
                    "Outgoing response",
                    type="response",
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
                )
        finally:
            AppLogger.reset_request_id(token)
