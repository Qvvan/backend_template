from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from src.core.container import Container
from src.entrypoints.consumer import create_consumer_app
from src.entrypoints.scheduler import create_scheduler_app
from src.interfaces.messaging.consumer import IConsumer
from src.interfaces.workers.worker import IWorker
from src.main import create_app
from src.workers.scheduler import AsyncScheduler
from tests.factories import make_config


class _StubWorker(IWorker):
    @property
    def name(self) -> str:
        return "stub"

    async def start(self, stop: asyncio.Event) -> None:
        await stop.wait()


class _StubConsumer(IConsumer):
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


def _container() -> Container:
    return Container(make_config())


def _route_paths(container: Container, factory_name: str) -> set[str]:
    factories = {"api": create_app, "consumer": create_consumer_app, "scheduler": create_scheduler_app}
    app = factories[factory_name](config=make_config(), container=container)
    return {getattr(route, "path", "") for route in app.routes}


def test_api_process_does_not_start_workers_or_consumers() -> None:
    container = _container()
    with TestClient(create_app(config=make_config(), container=container)):
        assert "scheduler" not in container.workers.__dict__
        assert "rabbitmq" not in container.consumers.__dict__


def test_scheduler_process_runs_workers_and_stops_them() -> None:
    container = _container()
    scheduler = AsyncScheduler(logger=container.logger, workers=[_StubWorker()])
    container.workers.__dict__["scheduler"] = scheduler  # pre-seed the cached_property

    with TestClient(create_scheduler_app(config=make_config(), container=container)) as client:
        assert scheduler.is_worker_running("stub")
        assert client.get("/api/v1/workers/").json()["workers"][0]["name"] == "stub"

    assert not scheduler.is_worker_running("stub")


def test_consumer_process_starts_and_stops_consumers() -> None:
    container = _container()
    rabbit, kafka = _StubConsumer(), _StubConsumer()
    container.consumers.__dict__.update(rabbitmq=rabbit, kafka=kafka)

    with TestClient(create_consumer_app(config=make_config(), container=container)):
        assert rabbit.started and kafka.started
        assert not rabbit.stopped

    assert rabbit.stopped and kafka.stopped


def test_workers_admin_api_lives_only_in_scheduler_process() -> None:
    assert not any(path.startswith("/api/v1/workers") for path in _route_paths(_container(), "api"))
    assert "/api/v1/workers/" in _route_paths(_container(), "scheduler")


def test_every_process_exposes_metrics() -> None:
    for name in ("api", "consumer", "scheduler"):
        assert "/metrics" in _route_paths(_container(), name)
