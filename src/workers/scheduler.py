import asyncio

from src.core.logger import AppLogger

from src.interfaces.workers.worker import IWorker


class AsyncScheduler:
    def __init__(
            self,
            logger: AppLogger,
            workers: list[IWorker],
    ) -> None:
        self.logger = logger
        self.workers = workers
        self.stop_events: dict[str, asyncio.Event] = {
            w.name: asyncio.Event() for w in workers
        }
        self._tasks: list[asyncio.Task[None]] = []

    def _register_tasks(self):
        self._tasks = [
            asyncio.create_task(
                w.start(self.stop_events[w.name])
            )
            for w in self.workers
        ]

    async def stop_worker(self, name: str) -> None:
        if name in self.stop_events:
            self.stop_events[name].set()
            self.logger.info(f"Worker {name} stopped")

    async def start_worker(self, name: str) -> None:
        worker = next((w for w in self.workers if w.name == name), None)
        if not worker:
            return

        self.stop_events[name] = asyncio.Event()
        task = asyncio.create_task(worker.start(self.stop_events[name]))
        self._tasks.append(task)
        self.logger.info(f"Worker {name} started")

    async def _stop_workers(self):
        """Останавливаем всех воркеров через их события"""
        for w in self.workers:
            if w.name in self.stop_events:
                self.stop_events[w.name].set()
                self.logger.info(f"Stop signal sent to {w.name}")

    def start(self) -> None:
        self.logger.info("Scheduler starting workers...")
        self._register_tasks()
        self.logger.info(f"Scheduler started {len(self._tasks)} workers")

    async def wait_until_done(self) -> None:
        if not self._tasks:
            return

        fut = asyncio.gather(*self._tasks, return_exceptions=True)
        await asyncio.wait_for(fut=fut, timeout=30.0)

    async def shutdown(self):
        self.logger.info("Shutting down scheduler...")
        await self._stop_workers()

        try:
            await self.wait_until_done()
            self.logger.info("All workers stopped gracefully")
        except asyncio.TimeoutError:
            self.logger.warning("Some workers didn't stop gracefully, cancelling...")
            for task in self._tasks:
                if not task.done():
                    task.cancel()

            await asyncio.gather(*self._tasks, return_exceptions=True)
            self.logger.info("All workers cancelled")
