from __future__ import annotations

from src.core.events import IntegrationEvent
from src.domain.entities.messaging import OutgoingMessage
from src.interfaces.messaging.publisher import IMessagePublisher


class FakeMessagePublisher(IMessagePublisher):
    """Records published messages; `fail_on` makes publishing of the given message ids raise."""

    def __init__(self, fail_on: frozenset[str] = frozenset()) -> None:
        self.published: list[OutgoingMessage] = []
        self._fail_on = fail_on

    async def publish(self, event: IntegrationEvent) -> None:
        await self.publish_message(event.to_message())

    async def publish_message(self, message: OutgoingMessage) -> None:
        if message.message_id in self._fail_on:
            raise ConnectionError("broker unavailable")
        self.published.append(message)
