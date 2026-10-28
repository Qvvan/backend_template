from __future__ import annotations

from typing import Protocol


class IHealthCheck(Protocol):
    """Any infrastructure client: returns True if the dependency is reachable, never raises."""

    async def health_check(self) -> bool: ...
