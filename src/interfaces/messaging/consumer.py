from __future__ import annotations

from abc import ABC, abstractmethod


class IConsumer(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Register all subscriptions; messages are then handled in the background until `stop()`."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        """Stop receiving new messages."""
        raise NotImplementedError
