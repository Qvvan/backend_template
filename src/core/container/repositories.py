from functools import cached_property

from src.core.container.infrastructure import InfrastructureContainer
from src.infrastructure.repository.redis.repository import RedisRepository


class RepositoryContainer:
    """Ленивая инициализация всех репозиториев."""

    __slots__ = "_infra"

    def __init__(self, infra: InfrastructureContainer) -> None:
        self._infra = infra


    @cached_property
    def redis(self) -> RedisRepository:
        return RedisRepository(client=self._infra.redis_db.client)

