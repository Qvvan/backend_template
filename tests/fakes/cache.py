from __future__ import annotations

import fnmatch

from src.interfaces.clients.cache_client.repository import ICacheRepository


class InMemoryCacheRepository(ICacheRepository):
    """ICacheRepository on a dict. TTLs are stored but never expire on their own."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, expire: int | None = None) -> bool:
        self.data[key] = value
        if expire is not None:
            self.ttls[key] = expire
        else:
            self.ttls.pop(key, None)
        return True

    async def delete(self, key: str) -> bool:
        self.ttls.pop(key, None)
        return self.data.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        return key in self.data

    async def expire(self, key: str, seconds: int) -> bool:
        if key not in self.data:
            return False
        self.ttls[key] = seconds
        return True

    async def ttl(self, key: str) -> int:
        if key not in self.data:
            return -2
        return self.ttls.get(key, -1)

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        return {key: self.data.get(key) for key in keys}

    async def set_many(self, mapping: dict[str, str], expire: int | None = None) -> bool:
        for key, value in mapping.items():
            await self.set(key, value, expire)
        return True

    async def delete_many(self, keys: list[str]) -> int:
        return sum([await self.delete(key) for key in keys])

    async def increment(self, key: str, amount: int = 1) -> int:
        value = int(self.data.get(key, "0")) + amount
        self.data[key] = str(value)
        return value

    async def decrement(self, key: str, amount: int = 1) -> int:
        return await self.increment(key, -amount)

    async def scan_keys(self, pattern: str = "*") -> list[str]:
        return [key for key in self.data if fnmatch.fnmatchcase(key, pattern)]
