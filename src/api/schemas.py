from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Body of every error response returned by the API."""

    status: Literal["error"] = "error"
    code: str
    comment: str
    obj: list[dict[str, Any]] | dict[str, Any] | None = None
    request_id: str | None = None
