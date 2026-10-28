from __future__ import annotations

from src.core.config import Config
from src.core.container.consumers import ConsumerContainer
from src.core.container.infrastructure import InfrastructureContainer
from src.core.container.repositories import RepositoryContainer
from src.core.container.services import ServiceContainer
from src.core.container.workers import WorkerContainer
from src.core.logger import AppLogger


class Container:
    __slots__ = ("_config", "consumers", "infra", "logger", "repos", "services", "workers")

    def __init__(self, config: Config) -> None:
        self._config = config
        self.logger = AppLogger(level=config.logging.LEVEL)
        self.infra = InfrastructureContainer(config, self.logger)
        self.repos = RepositoryContainer(self.infra)
        self.services = ServiceContainer(
            config=config,
            logger=self.logger,
            infra=self.infra,
            repos=self.repos,
        )
        self.workers = WorkerContainer(config=config, logger=self.logger, services=self.services)
        self.consumers = ConsumerContainer(logger=self.logger, infra=self.infra, services=self.services)

    async def closer(self) -> None:
        await self.consumers.stop()
        await self.workers.close()
        await self.infra.close()
        self.logger.info("All connections closed")


__all__ = [
    "ConsumerContainer",
    "Container",
    "InfrastructureContainer",
    "RepositoryContainer",
    "ServiceContainer",
    "WorkerContainer",
]
