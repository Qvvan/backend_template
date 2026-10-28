from __future__ import annotations

import asyncio
from collections.abc import Mapping

from src.core.logger import AppLogger
from src.domain.entities.health import HealthReportEntity
from src.interfaces.clients.health import IHealthCheck
from src.interfaces.services.health_service import IHealthService


class HealthService(IHealthService):
    __slots__ = ("_checks", "_logger", "_timeout")

    def __init__(self, checks: Mapping[str, IHealthCheck], logger: AppLogger, timeout: float = 5.0) -> None:
        self._checks = checks
        self._logger = logger
        self._timeout = timeout

    async def check_dependencies(self) -> HealthReportEntity:
        names = list(self._checks)
        results = await asyncio.gather(*(self._check(name) for name in names))
        return HealthReportEntity(checks=dict(zip(names, results, strict=True)))

    async def _check(self, name: str) -> bool:
        try:
            async with asyncio.timeout(self._timeout):
                return await self._checks[name].health_check()
        except Exception:
            self._logger.warning("Health check did not complete", component=name, timeout_seconds=self._timeout)
            return False
