from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.messaging import OutgoingMessage


class IOutboxRepository(ABC):
    """Transactional outbox: messages are stored in the same transaction as the business change
    and published later by the outbox relay worker."""

    @abstractmethod
    async def add(self, message: OutgoingMessage) -> None:
        raise NotImplementedError

    @abstractmethod
    async def fetch_pending(self, limit: int) -> list[OutgoingMessage]:
        """Oldest unpublished messages, locked until the end of the transaction (skips rows locked by others)."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, message_ids: list[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def mark_failed(self, message_id: str, error: str) -> None:
        raise NotImplementedError
