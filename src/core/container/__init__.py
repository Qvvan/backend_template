from src.core.config import Config
from src.core.container.infrastructure import InfrastructureContainer
from src.core.container.repositories import RepositoryContainer
from src.core.container.services import ServiceContainer
from src.core.container.workers import WorkerContainer
from src.core.logger import AppLogger


class Container:
    """
    Собирает подконтейнеры и предоставляет общий логгер и shutdown.

    """

    __slots__ = ("config", "infra", "logger", "repos", "services", "workers")

    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = AppLogger(level=config.logging.LEVEL)
        self.infra = InfrastructureContainer(config, self.logger)
        self.repos = RepositoryContainer(self.infra)
        self.services = ServiceContainer(
            infra=self.infra,
            repos=self.repos,
        )
        self.workers = WorkerContainer(logger=self.logger, services=self.services)

    async def closer(self) -> None:
        await self.workers.close()
        await self.infra.close()
        self.logger.info("All connections closed")


__all__ = [
    "Container",
    "InfrastructureContainer",
    "RepositoryContainer",
    "ServiceContainer",
    "WorkerContainer",
]
