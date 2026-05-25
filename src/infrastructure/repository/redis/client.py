from __future__ import annotations

import redis.asyncio as aioredis

from src.core.logger import AppLogger
from src.interfaces.clients.cache_client.client import ICacheDB


class RedisDB(ICacheDB):
    """Обёртка над Redis async client."""

    __slots__ = ("_client", "_logger")

    def __init__(
        self,
        logger: AppLogger,
        host: str,
        port: int,
        db: int = 0,
        password: str | None = None,
        decode_responses: bool = True,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
    ) -> None:
        self._logger = logger
        self._client = aioredis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
        )

    @property
    def client(self) -> aioredis.Redis:
        return self._client

    async def close(self) -> None:
        """Закрыть подключение."""
        await self._client.close()

    async def health_check(self) -> bool:
        try:
            return await self._client.ping()  # type: ignore[misc]
        except Exception as e:
            self._logger.error("Redis health check failed", error=e)
            return False
