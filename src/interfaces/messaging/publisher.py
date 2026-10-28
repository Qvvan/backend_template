from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.events import IntegrationEvent
from src.domain.entities.messaging import OutgoingMessage


class IMessagePublisher(ABC):
    """Publishes integration events; the broker (RabbitMQ or Kafka) is chosen in the container."""

    @abstractmethod
    async def publish(self, event: IntegrationEvent) -> None:
        """Publish an event right now (not atomic with DB changes — use the outbox for that)."""
        raise NotImplementedError

    @abstractmethod
    async def publish_message(self, message: OutgoingMessage) -> None:
        """Publish an already serialized message (used by the outbox relay)."""
        raise NotImplementedError
