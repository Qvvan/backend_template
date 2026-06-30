from __future__ import annotations

from functools import cached_property

from src.core.container.services import ServiceContainer
from src.core.logger import AppLogger
from src.interfaces.workers.worker import IWorker
from src.workers.scheduler import AsyncScheduler


class WorkerContainer:
    """Контейнер фоновых воркеров и их планировщика.

    Чтобы зарегистрировать воркер:
      1. Добавь его экземпляр в список `all_workers`.
      2. Если воркер должен стартовать автоматически — добавь его имя в `auto_start`.
         Если `auto_start=None`, стартуют все воркеры (поведение по умолчанию).
         Если `auto_start=frozenset()`, ни один воркер не стартует автоматически.
    """

    def __init__(self, logger: AppLogger, services: ServiceContainer) -> None:
        self._logger = logger
        self._services = services

    @cached_property
    def scheduler(self) -> AsyncScheduler:
        all_workers: list[IWorker] = [
            # Пример:
            # CleanupWorker(service=self._services.cleanup, logger=self._logger, interval=60),
        ]
        auto_start: frozenset[str] | None = None  # None = стартуют все
        return AsyncScheduler(
            logger=self._logger,
            workers=all_workers,
            auto_start=auto_start,
        )

    def start(self) -> None:
        self.scheduler.start()

    async def close(self) -> None:
        await self.scheduler.shutdown()
