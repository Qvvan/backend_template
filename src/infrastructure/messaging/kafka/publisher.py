from __future__ import annotations

from src.core.events import IntegrationEvent
from src.domain.entities.messaging import OutgoingMessage
from src.interfaces.messaging.kafka.client import IKafkaClient
from src.interfaces.messaging.publisher import IMessagePublisher


class KafkaMessagePublisher(IMessagePublisher):
    """Publishes integration events to Kafka: destination = topic, routing_key goes to `x-event-type`."""

    __slots__ = ("_kafka",)

    def __init__(self, kafka: IKafkaClient) -> None:
        self._kafka = kafka

    async def publish(self, event: IntegrationEvent) -> None:
        await self.publish_message(event.to_message())

    async def publish_message(self, message: OutgoingMessage) -> None:
        await self._kafka.publish(
            topic=message.destination,
            payload=message.payload,
            key=message.key,
            headers=message.headers,
            message_id=message.message_id,
        )
