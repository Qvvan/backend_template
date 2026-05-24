import redis.asyncio as aioredis

from src.interfaces.clients.cache_client.client import ICacheDB


class RedisDB(ICacheDB):
    """Обёртка над Redis async client."""

    def __init__(
        self,
        host: str,
        port: int,
        db: int = 0,
        password: str | None = None,
        decode_responses: bool = True,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
    ) -> None:
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
        """Получить Redis клиент."""
        return self._client

    async def close(self) -> None:
        """Закрыть подключение."""
        await self._client.close()
