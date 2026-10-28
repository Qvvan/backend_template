from __future__ import annotations

from src.core.events import IntegrationEvent
from src.domain.entities.messaging import OutgoingMessage
from src.interfaces.messaging.publisher import IMessagePublisher
from src.interfaces.messaging.rabbitmq.client import IAMQPClient


class RabbitMQMessagePublisher(IMessagePublisher):
    """Publishes integration events to RabbitMQ: destination = exchange, routing_key = routing key."""

    __slots__ = ("_rabbit",)

    def __init__(self, rabbit: IAMQPClient) -> None:
        self._rabbit = rabbit

    async def publish(self, event: IntegrationEvent) -> None:
        await self.publish_message(event.to_message())

    async def publish_message(self, message: OutgoingMessage) -> None:
        await self._rabbit.publish(
            exchange=message.destination,
            routing_key=message.routing_key,
            payload=message.payload,
            headers=message.headers,
            message_id=message.message_id,
        )
