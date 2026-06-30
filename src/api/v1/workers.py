from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette import status

from src.api.dependencies import get_scheduler
from src.api.v1.schemas.worker_schemas import WorkerResponse, WorkersListResponse
from src.core.exceptions import NotFoundError
from src.interfaces.workers.scheduler import IScheduler

router = APIRouter(prefix="/workers", tags=["Workers"])


@router.get(
    "/",
    response_model=WorkersListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all registered workers and their status",
)
async def list_workers(scheduler: IScheduler = Depends(get_scheduler)) -> WorkersListResponse:
    workers = scheduler.list_workers()
    return WorkersListResponse(
        workers=[WorkerResponse(**w) for w in workers],
        total=len(workers),
    )


@router.get(
    "/{name}",
    response_model=WorkerResponse,
    status_code=status.HTTP_200_OK,
    summary="Get status of a specific worker",
)
async def get_worker(name: str, scheduler: IScheduler = Depends(get_scheduler)) -> WorkerResponse:
    if not scheduler.worker_exists(name):
        raise NotFoundError("Worker", name)
    return WorkerResponse(**scheduler.get_worker_info(name))


@router.post(
    "/{name}/start",
    response_model=WorkerResponse,
    status_code=status.HTTP_200_OK,
    summary="Start a worker",
)
async def start_worker(name: str, scheduler: IScheduler = Depends(get_scheduler)) -> WorkerResponse:
    if not scheduler.worker_exists(name):
        raise NotFoundError("Worker", name)
    await scheduler.start_worker(name)
    return WorkerResponse(**scheduler.get_worker_info(name))


@router.post(
    "/{name}/stop",
    response_model=WorkerResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop a worker",
)
async def stop_worker(name: str, scheduler: IScheduler = Depends(get_scheduler)) -> WorkerResponse:
    if not scheduler.worker_exists(name):
        raise NotFoundError("Worker", name)
    await scheduler.stop_worker(name)
    return WorkerResponse(**scheduler.get_worker_info(name))
