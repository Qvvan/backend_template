from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.container import Container
from src.core.logger import AppLogger
from src.main import create_app
from tests.factories import make_config


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require running infrastructure)",
    )


@pytest.fixture
def logger() -> AppLogger:
    return AppLogger(level="DEBUG")


@pytest.fixture
def container() -> Container:
    """Real container on a test config: nothing connects until a client is used."""
    return Container(make_config())


@pytest.fixture
def api_app(container: Container) -> FastAPI:
    """The real API app. Replace services with fakes via `api_app.dependency_overrides[get_x_service]`."""
    return create_app(config=make_config(), container=container)


@pytest.fixture
def api_client(api_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(api_app, raise_server_exceptions=False) as client:
        yield client
    api_app.dependency_overrides.clear()
