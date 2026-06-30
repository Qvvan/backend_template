from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette import status
from starlette.exceptions import HTTPException

from src.api.dependencies import get_kafka, get_minio, get_postgres_db, get_rabbitmq, get_redis
from src.interfaces.clients.cache_client.client import ICacheDB
from src.interfaces.clients.db.connection import IDBTransactional
from src.interfaces.clients.storage.client import IStorageClient
from src.interfaces.messaging.kafka.client import IKafkaClient
from src.interfaces.messaging.rabbitmq.client import IAMQPClient

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    path="/",
    status_code=status.HTTP_200_OK,
    summary="Health check",
)
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
    }


@router.get(
    "/postgresql",
    status_code=status.HTTP_200_OK,
    summary="PostgreSQL dependency health check",
)
async def health_check_postgresql(postgres_db: IDBTransactional = Depends(get_postgres_db)) -> dict[str, str]:
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
async def health_check_rabbitmq(rabbitmq: IAMQPClient = Depends(get_rabbitmq)) -> dict[str, str]:
    """Проверка доступности BackendRabbitMQ."""
    health_status = await rabbitmq.health_check()
    if not health_status:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BackendRabbitMQ is unavailable",
        )

    return {"status": "ok"}


@router.get(
    "/kafka",
    status_code=status.HTTP_200_OK,
    summary="Kafka dependency health check",
)
async def health_check_kafka(kafka: IKafkaClient = Depends(get_kafka)) -> dict[str, str]:
    """Проверка доступности Kafka."""
    health_status = await kafka.health_check()
    if not health_status:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kafka is unavailable",
        )

    return {"status": "ok"}


@router.get(
    "/redis",
    status_code=status.HTTP_200_OK,
    summary="Redis dependency health check",
)
async def health_check_redis(redis: ICacheDB = Depends(get_redis)) -> dict[str, str]:
    """Проверка доступности Redis."""
    health_status = await redis.health_check()
    if not health_status:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable",
        )

    return {"status": "ok"}


@router.get(
    "/minio",
    status_code=status.HTTP_200_OK,
    summary="MinIO dependency health check",
)
async def health_check_minio(storage: IStorageClient = Depends(get_minio)) -> dict[str, str]:
    """Проверка доступности MinIO."""
    health_status = await storage.health_check()
    if not health_status:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MinIO is unavailable",
        )

    return {"status": "ok"}
