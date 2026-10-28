from __future__ import annotations

import asyncio
import contextlib
from abc import abstractmethod

from src.core.logger import AppLogger
from src.interfaces.workers.worker import IWorker


class PeriodicWorker(IWorker):
    """Base for workers that call a service every `interval` seconds.

    Subclasses define `name` and `tick()`. An exception in `tick()` is logged and the worker keeps
    running; the stop event interrupts the pause between ticks immediately.
    """

    __slots__ = ("_interval", "_logger")

    def __init__(self, logger: AppLogger, interval: float) -> None:
        self._logger = logger
        self._interval = interval

    @abstractmethod
    async def tick(self) -> None:
        raise NotImplementedError

    async def start(self, stop: asyncio.Event) -> None:
        self._logger.info("Worker started", worker_name=self.name, interval_seconds=self._interval)
        while not stop.is_set():
            try:
                await self.tick()
            except Exception:
                self._logger.error("Worker tick failed", worker_name=self.name)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self._interval)
        self._logger.info("Worker stopped", worker_name=self.name)
