from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


class ErrorResponse(BaseModel):
    """Body of every error response returned by the API."""

    status: Literal["error"] = "error"
    code: str
    comment: str
    obj: list[dict[str, Any]] | dict[str, Any] | None = None
    request_id: str | None = None


HealthStatus = Literal["ok", "error"]


class LivenessResponse(BaseModel):
    status: HealthStatus


class ReadinessResponse(BaseModel):
    status: HealthStatus
    checks: dict[str, HealthStatus]
