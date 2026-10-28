from __future__ import annotations

from abc import ABC, abstractmethod


class IOutboxRelayService(ABC):
    @abstractmethod
    async def relay_batch(self) -> int:
        """Publish one batch of pending outbox messages; returns how many were published."""
        raise NotImplementedError
