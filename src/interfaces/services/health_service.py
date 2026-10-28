from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.health import HealthReportEntity


class IHealthService(ABC):
    @abstractmethod
    async def check_dependencies(self) -> HealthReportEntity:
        """Check every dependency concurrently."""
        raise NotImplementedError
