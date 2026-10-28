from __future__ import annotations

from abc import ABC, abstractmethod


class IInboxRepository(ABC):
    """Inbox for idempotent consumers: remembers which messages a consumer has already processed."""

    @abstractmethod
    async def register(self, message_id: str, consumer: str) -> bool:
        """Record the message as processed by `consumer`.

        Returns False if it was already recorded (a redelivery) — the caller should skip it.
        Call inside the same transaction as the business change.
        """
        raise NotImplementedError
