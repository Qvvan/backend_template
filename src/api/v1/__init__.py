from __future__ import annotations

from fastapi import APIRouter

v1_router = APIRouter(prefix="/v1")

# scaffold:v1-routers

__all__ = ["v1_router"]
