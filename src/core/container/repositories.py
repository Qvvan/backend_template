from __future__ import annotations

from functools import cached_property

from src.core.container.infrastructure import InfrastructureContainer
from src.infrastructure.repository.redis.repository import RedisRepository
from src.interfaces.clients.cache_client.repository import ICacheRepository


class RepositoryContainer:
    """Ленивая инициализация всех репозиториев."""

    def __init__(self, infra: InfrastructureContainer) -> None:
        self._infra = infra

    @cached_property
    def redis(self) -> ICacheRepository:
        return RedisRepository(client=self._infra.redis_db.client)
