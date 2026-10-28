from __future__ import annotations

import asyncio

from src.core.logger import AppLogger
from src.workers.periodic import PeriodicWorker


class _CountingWorker(PeriodicWorker):
    def __init__(self, interval: float, fail_first: bool = False) -> None:
        super().__init__(logger=AppLogger(level="DEBUG"), interval=interval)
        self.ticks = 0
        self._fail_first = fail_first

    @property
    def name(self) -> str:
        return "counting"

    async def tick(self) -> None:
        self.ticks += 1
        if self._fail_first and self.ticks == 1:
            raise RuntimeError("first tick fails")


async def test_worker_ticks_until_stopped() -> None:
    worker = _CountingWorker(interval=0.01)
    stop = asyncio.Event()
    task = asyncio.create_task(worker.start(stop))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    assert worker.ticks >= 2


async def test_stop_interrupts_long_interval_immediately() -> None:
    worker = _CountingWorker(interval=60)
    stop = asyncio.Event()
    task = asyncio.create_task(worker.start(stop))
    await asyncio.sleep(0.01)
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    assert worker.ticks == 1


async def test_failing_tick_does_not_stop_worker() -> None:
    worker = _CountingWorker(interval=0.01, fail_first=True)
    stop = asyncio.Event()
    task = asyncio.create_task(worker.start(stop))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    assert worker.ticks >= 2
