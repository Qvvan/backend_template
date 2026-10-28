from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from src.api.middleware.request_logging import REQUEST_ID_HEADER
from src.api.schemas import ErrorResponse
from src.core.exceptions import AppError, ErrorCode

_HTTP_STATUS_CODES: dict[int, ErrorCode] = {
    status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
}


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    comment: str,
    obj: list[dict[str, Any]] | dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id: str | None = getattr(request.state, "request_id", None)
    response_headers = dict(headers or {})
    if request_id:
        # Responses produced by ServerErrorMiddleware bypass RequestLoggingMiddleware, so set it here too.
        response_headers[REQUEST_ID_HEADER] = request_id
    body = ErrorResponse(code=code, comment=comment, obj=obj, request_id=request_id)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"), headers=response_headers)


def register_errors(app: FastAPI) -> None:
    """Every error leaves the API as ErrorResponse: {status, code, comment, obj, request_id}."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(request, status_code=exc.http_status_code, code=exc.code, comment=exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in exc.errors()]
        return _error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=ErrorCode.VALIDATION_ERROR,
            comment="Request validation failed",
            obj=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(
            request,
            status_code=exc.status_code,
            code=_HTTP_STATUS_CODES.get(exc.status_code, ErrorCode.HTTP_ERROR),
            comment=str(exc.detail),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
        # The exception itself is logged by RequestLoggingMiddleware; the client gets no internals.
        return _error_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
            comment="Internal server error",
        )
