from __future__ import annotations

import asyncio

from src.core.logger import AppLogger
from src.interfaces.workers.scheduler import IScheduler, WorkerInfo
from src.interfaces.workers.worker import IWorker


class AsyncScheduler(IScheduler):
    """Планировщик фоновых воркеров с поддержкой авто-старта и управления через API."""

    __slots__ = ("_auto_start", "_logger", "_stop_events", "_tasks", "_workers")

    def __init__(
        self,
        logger: AppLogger,
        workers: list[IWorker],
        auto_start: frozenset[str] | None = None,
    ) -> None:
        self._logger = logger
        self._workers = workers
        self._auto_start = auto_start  # None = все воркеры; frozenset = только перечисленные
        self._stop_events: dict[str, asyncio.Event] = {w.name: asyncio.Event() for w in workers}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    # ------------------------------------------------------------------
    # IScheduler
    # ------------------------------------------------------------------

    def worker_exists(self, name: str) -> bool:
        return any(w.name == name for w in self._workers)

    def is_worker_running(self, name: str) -> bool:
        task = self._tasks.get(name)
        return task is not None and not task.done()

    def get_worker_info(self, name: str) -> WorkerInfo:
        return WorkerInfo(
            name=name,
            running=self.is_worker_running(name),
            auto_start=self._auto_start is None or name in self._auto_start,
        )

    def list_workers(self) -> list[WorkerInfo]:
        return [self.get_worker_info(w.name) for w in self._workers]

    async def start_worker(self, name: str) -> None:
        worker = next((w for w in self._workers if w.name == name), None)
        if not worker:
            return
        if self.is_worker_running(name):
            self._logger.debug("Worker already running", worker_name=name)
            return
        self._stop_events[name] = asyncio.Event()
        self._tasks[name] = asyncio.create_task(worker.start(self._stop_events[name]))
        self._logger.info("Worker started", worker_name=name)

    async def stop_worker(self, name: str) -> None:
        if not self.is_worker_running(name):
            return
        self._stop_events[name].set()
        task = self._tasks.get(name)
        if task:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=10.0)
            except TimeoutError:
                self._logger.warning("Worker did not stop in time", worker_name=name)
            except Exception as e:
                self._logger.warning("Worker raised during stop", worker_name=name, error=e)
        self._tasks.pop(name, None)
        self._logger.info("Worker stopped", worker_name=name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _should_auto_start(self, name: str) -> bool:
        return self._auto_start is None or name in self._auto_start

    def _register_tasks(self) -> None:
        for w in self._workers:
            if self._should_auto_start(w.name):
                self._tasks[w.name] = asyncio.create_task(w.start(self._stop_events[w.name]))

    def start(self) -> None:
        self._logger.info("Scheduler starting workers...")
        self._register_tasks()
        self._logger.info("Scheduler started workers", count_workers=len(self._tasks))

    async def wait_until_done(self) -> None:
        if not self._tasks:
            return
        _, pending = await asyncio.wait(list(self._tasks.values()), timeout=30.0)
        if pending:
            raise TimeoutError

    async def shutdown(self) -> None:
        self._logger.info("Shutting down scheduler...")
        for w in self._workers:
            if self.is_worker_running(w.name):
                self._stop_events[w.name].set()
                self._logger.info("Stop signal sent", worker_name=w.name)
        try:
            await self.wait_until_done()
            self._logger.info("All workers stopped gracefully")
        except TimeoutError:
            self._logger.warning("Some workers did not stop in time, cancelling...")
            for task in self._tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
            self._logger.info("All workers cancelled")
