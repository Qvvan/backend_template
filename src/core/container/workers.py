from functools import cached_property

from src.core.logger import AppLogger
from src.core.container.services import ServiceContainer
from src.workers.scheduler import AsyncScheduler


class WorkerContainer:
    """Контейнер фоновых воркеров и их планировщика."""
    def __init__(self, logger: AppLogger, services: ServiceContainer) -> None:
        self._logger = logger
        self._services = services


    @cached_property
    def scheduler(self) -> AsyncScheduler:
            return AsyncScheduler(
                logger=self._logger,
                workers=[],
            )

    def start(self) -> None:
        self.scheduler.start()

    async def close(self) -> None:
            await self.scheduler.shutdown()
