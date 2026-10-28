from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HealthReportEntity:
    """Result of dependency checks: component name -> is it reachable."""

    checks: dict[str, bool]

    @property
    def is_ready(self) -> bool:
        return all(self.checks.values())
