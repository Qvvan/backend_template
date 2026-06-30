from __future__ import annotations

from pydantic import BaseModel


class WorkerResponse(BaseModel):
    name: str
    running: bool
    auto_start: bool


class WorkersListResponse(BaseModel):
    workers: list[WorkerResponse]
    total: int
