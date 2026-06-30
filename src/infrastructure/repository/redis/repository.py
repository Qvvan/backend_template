from __future__ import annotations

import redis.asyncio as aioredis

from src.interfaces.clients.cache_client.repository import ICacheRepository


class RedisRepository(ICacheRepository):
    """Реализация репозитория для работы с Redis."""

    __slots__ = ("_client",)

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        """Получить значение по ключу."""
        return await self._client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        expire: int | None = None,
    ) -> bool:
        """Установить значение по ключу."""
        if expire is not None:
            return await self._client.setex(key, expire, value)
        return await self._client.set(key, value)

    async def delete(self, key: str) -> bool:
        """Удалить ключ."""
        result = await self._client.delete(key)
        return result > 0

    async def exists(self, key: str) -> bool:
        """Проверить существование ключа."""
        result = await self._client.exists(key)
        return result > 0

    async def expire(self, key: str, seconds: int) -> bool:
        """Установить время жизни ключа в секундах."""
        return await self._client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Получить оставшееся время жизни ключа в секундах."""
        return await self._client.ttl(key)

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        """Получить несколько значений по ключам."""
        if not keys:
            return {}
        values = await self._client.mget(keys)
        return dict(zip(keys, values, strict=True))

    async def set_many(
        self,
        mapping: dict[str, str],
        expire: int | None = None,
    ) -> bool:
        if not mapping:
            return True
        if expire is not None:
            async with self._client.pipeline() as pipe:
                for key, value in mapping.items():
                    pipe.setex(key, expire, value)
                results = await pipe.execute()
            return all(not isinstance(r, Exception) for r in results)
        await self._client.mset(mapping)
        return True

    async def delete_many(self, keys: list[str]) -> int:
        """Удалить несколько ключей. Возвращает количество удалённых ключей."""
        if not keys:
            return 0
        return await self._client.delete(*keys)

    async def increment(self, key: str, amount: int = 1) -> int:
        """Увеличить значение на amount. Возвращает новое значение."""
        return await self._client.incrby(key, amount)

    async def decrement(self, key: str, amount: int = 1) -> int:
        """Уменьшить значение на amount. Возвращает новое значение."""
        return await self._client.decrby(key, amount)

    async def scan_keys(self, pattern: str = "*") -> list[str]:
        return [key async for key in self._client.scan_iter(pattern)]
