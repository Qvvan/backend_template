from __future__ import annotations

import pytest

from src.core.logger import AppLogger


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require running infrastructure)",
    )


@pytest.fixture
def logger() -> AppLogger:
    return AppLogger(level="DEBUG")
