from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_health_service
from src.api.exception_handlers import register_errors
from src.api.health import router
from src.core.logger import AppLogger
from src.services.health_service import HealthService


class _Check:
    def __init__(self, result: bool | None = True, delay: float = 0.0) -> None:
        self._result = result
        self._delay = delay

    async def health_check(self) -> bool:
        await asyncio.sleep(self._delay)
        if self._result is None:
            raise RuntimeError("client bug: health_check must not raise")
        return self._result


def _service(**checks: _Check) -> HealthService:
    return HealthService(checks=checks, logger=AppLogger(level="DEBUG"), timeout=0.2)


def _client(service: HealthService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    register_errors(app)
    app.dependency_overrides[get_health_service] = lambda: service
    return TestClient(app)


# ── HealthService ─────────────────────────────────────────────────────────────


async def test_all_checks_pass() -> None:
    report = await _service(postgres=_Check(True), redis=_Check(True)).check_dependencies()
    assert report.checks == {"postgres": True, "redis": True}
    assert report.is_ready


async def test_failed_check_makes_report_not_ready() -> None:
    report = await _service(postgres=_Check(True), redis=_Check(False)).check_dependencies()
    assert report.checks == {"postgres": True, "redis": False}
    assert not report.is_ready


@pytest.mark.parametrize("check", [_Check(True, delay=1.0), _Check(None)])
async def test_slow_or_raising_check_counts_as_failed(check: _Check) -> None:
    report = await _service(slow=check).check_dependencies()
    assert report.checks == {"slow": False}


async def test_checks_run_concurrently() -> None:
    started = asyncio.get_running_loop().time()
    await _service(a=_Check(delay=0.1), b=_Check(delay=0.1), c=_Check(delay=0.1)).check_dependencies()
    assert asyncio.get_running_loop().time() - started < 0.25


# ── endpoints ─────────────────────────────────────────────────────────────────


def test_livez_is_always_ok() -> None:
    response = _client(_service(postgres=_Check(False))).get("/livez")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_ok_when_all_dependencies_are_up() -> None:
    response = _client(_service(postgres=_Check(True), redis=_Check(True))).get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


def test_readyz_503_lists_failed_dependency() -> None:
    response = _client(_service(postgres=_Check(True), redis=_Check(False))).get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "checks": {"postgres": "ok", "redis": "error"}}
