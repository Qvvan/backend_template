from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from starlette import status

from src.api.dependencies import get_health_service
from src.api.schemas import LivenessResponse, ReadinessResponse
from src.interfaces.services.health_service import IHealthService

router = APIRouter(tags=["Health"])


@router.get("/livez", summary="Liveness probe: the process is up", response_model=LivenessResponse)
async def livez() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/readyz",
    summary="Readiness probe: all dependencies are reachable (503 otherwise)",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readyz(response: Response, service: IHealthService = Depends(get_health_service)) -> ReadinessResponse:
    report = await service.check_dependencies()
    if not report.is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ok" if report.is_ready else "error",
        checks={name: "ok" if healthy else "error" for name, healthy in report.checks.items()},
    )
