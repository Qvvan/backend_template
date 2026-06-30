from __future__ import annotations

from fastapi import APIRouter

from src.api.v1.workers import router as workers_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(workers_router)

__all__ = ["v1_router"]
