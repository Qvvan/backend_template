from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.core.logger import AppLogger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования HTTP запросов."""

    def __init__(self, app: ASGIApp, logger: AppLogger) -> None:
        super().__init__(app)
        self.logger = logger

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        AppLogger.set_request_id(request_id)

        self.logger.info(
            "Incoming request",
            type="request",
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            user_agent=request.headers.get("user-agent", ""),
        )

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                "Outgoing response failed",
                type="response",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error_type=type(exc).__name__,
            )
            raise
        else:
            response.headers["X-Request-ID"] = request_id
            self.logger.info(
                "Outgoing response",
                type="response",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            return response
        finally:
            AppLogger.clear_request_id()
