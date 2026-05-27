from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.core.logger import AppLogger
from src.interfaces.workers.worker import IWorker
from src.workers.scheduler import AsyncScheduler


class _StubWorker(IWorker):
    __slots__ = ("_name", "started", "stopped")

    def __init__(self, name: str) -> None:
        self._name = name
        self.started = False
        self.stopped = False

    @property
    def name(self) -> str:
        return self._name

    async def start(self, stop: asyncio.Event) -> None:
        self.started = True
        await stop.wait()
        self.stopped = True


class _RaisingWorker(IWorker):
    __slots__ = ("_name",)

    def __init__(self) -> None:
        self._name = "raising"

    @property
    def name(self) -> str:
        return self._name

    async def start(self, stop: asyncio.Event) -> None:
        await stop.wait()
        raise RuntimeError("worker exploded")


@pytest.fixture
def app_logger() -> AppLogger:
    return AppLogger(level="DEBUG")


async def test_start_creates_tasks_for_each_worker(app_logger: AppLogger) -> None:
    workers = [_StubWorker("w1"), _StubWorker("w2")]
    scheduler = AsyncScheduler(logger=app_logger, workers=workers)
    scheduler.start()
    await asyncio.sleep(0)
    assert all(w.started for w in workers)
    await scheduler.shutdown()


async def test_shutdown_signals_all_workers(app_logger: AppLogger) -> None:
    workers = [_StubWorker("a"), _StubWorker("b")]
    scheduler = AsyncScheduler(logger=app_logger, workers=workers)
    scheduler.start()
    await asyncio.sleep(0)
    await scheduler.shutdown()
    assert all(w.stopped for w in workers)


async def test_stop_single_worker_by_name(app_logger: AppLogger) -> None:
    w1 = _StubWorker("w1")
    w2 = _StubWorker("w2")
    scheduler = AsyncScheduler(logger=app_logger, workers=[w1, w2])
    scheduler.start()
    await asyncio.sleep(0)
    await scheduler.stop_worker("w1")
    assert w1.stopped is True
    assert w2.stopped is False
    await scheduler.shutdown()


async def test_stop_nonexistent_worker_does_not_raise(app_logger: AppLogger) -> None:
    scheduler = AsyncScheduler(logger=app_logger, workers=[])
    await scheduler.stop_worker("does-not-exist")


async def test_start_worker_after_stop(app_logger: AppLogger) -> None:
    worker = _StubWorker("w1")
    scheduler = AsyncScheduler(logger=app_logger, workers=[worker])
    scheduler.start()
    await asyncio.sleep(0)

    await scheduler.stop_worker("w1")
    assert worker.stopped is True

    worker.started = False
    worker.stopped = False
    await scheduler.start_worker("w1")
    await asyncio.sleep(0)
    assert worker.started is True

    await scheduler.shutdown()
    assert worker.stopped is True


async def test_shutdown_with_empty_worker_list(app_logger: AppLogger) -> None:
    scheduler = AsyncScheduler(logger=app_logger, workers=[])
    scheduler.start()
    await scheduler.shutdown()


async def test_raising_worker_does_not_hang_shutdown(app_logger: AppLogger) -> None:
    worker = _RaisingWorker()
    scheduler = AsyncScheduler(logger=app_logger, workers=[worker])
    scheduler.start()
    await asyncio.sleep(0)
    await scheduler.shutdown()


# ── lines 33-34: exception swallowed in stop_worker ──────────────────────────


async def test_stop_worker_swallows_exception_from_raising_worker(app_logger: AppLogger) -> None:
    # _RaisingWorker raises RuntimeError after stop event is set.
    # stop_worker must catch it and log a warning — not propagate.
    worker = _RaisingWorker()
    scheduler = AsyncScheduler(logger=app_logger, workers=[worker])
    scheduler.start()
    await asyncio.sleep(0)

    await scheduler.stop_worker("raising")  # must not raise


# ── line 41: early return in start_worker when name not found ─────────────────


async def test_start_nonexistent_worker_does_not_raise(app_logger: AppLogger) -> None:
    scheduler = AsyncScheduler(logger=app_logger, workers=[])
    await scheduler.start_worker("does-not-exist")  # must return silently


# ── lines 72-78: timeout path in shutdown cancels tasks ──────────────────────


async def test_shutdown_timeout_cancels_pending_tasks(app_logger: AppLogger) -> None:
    worker = _StubWorker("w1")
    scheduler = AsyncScheduler(logger=app_logger, workers=[worker])
    scheduler.start()
    await asyncio.sleep(0)

    # Simulate wait_until_done timing out without actually waiting 30 s.
    # patch.object on the class (not the instance) is required because
    # AsyncScheduler uses __slots__, which makes instance attributes read-only.
    with patch.object(AsyncScheduler, "wait_until_done", AsyncMock(side_effect=TimeoutError)):
        await scheduler.shutdown()  # must complete without raising
