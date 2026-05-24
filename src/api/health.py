from fastapi import APIRouter, Depends

from src.api.dependencies import get_postgres_db, get_rabbitmq, get_redis
from src.interfaces.clients.cache_client.client import ICacheDB
from src.interfaces.clients.db.connection import IDBBase
from starlette import status
from starlette.exceptions import HTTPException

from src.interfaces.messaging.rabbitmq import IAMQPClient

router = APIRouter(prefix="/health", tags=["Health"])

@router.get(
    path="/",
    status_code=status.HTTP_200_OK,
    summary="Health check",
)
async def health_check():
    return {
        "status": "ok",
    }


@router.get(
    "/postgresql",
    status_code=status.HTTP_200_OK,
    summary="PostgreSQL dependency health check",
)
async def health_check_postgresql(postgres_db: IDBBase = Depends(get_postgres_db)):
    """Проверка доступности Postgres DB."""
    health_status = await postgres_db.health_check()
    if not health_status:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Postgres DB is unavailable",
        )

    return {"status": "ok"}


@router.get(
    "/rabbitmq",
    status_code=status.HTTP_200_OK,
    summary="BackendRabbitMQ dependency health check",
)
async def health_check_rabbitmq(rabbitmq: IAMQPClient = Depends(get_rabbitmq)):
    """Проверка доступности BackendRabbitMQ."""
    health_status = await rabbitmq.health_check()
    if not health_status:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BackendRabbitMQ is unavailable",
        )

    return {"status": "ok"}

@router.get(
    "/redis",
    status_code=status.HTTP_200_OK,
    summary="Redis dependency health check",
)
async def health_check_redis(redis: ICacheDB = Depends(get_redis)):
    """Проверка доступности BackendRabbitMQ."""
    health_status = await redis.health_check()
    if not health_status:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable",
        )

    return {"status": "ok"}