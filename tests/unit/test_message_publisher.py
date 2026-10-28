from __future__ import annotations

from typing import ClassVar
from unittest.mock import AsyncMock

from src.core.events import IntegrationEvent
from src.domain.entities.messaging import OutgoingMessage
from src.infrastructure.messaging.kafka.publisher import KafkaMessagePublisher
from src.infrastructure.messaging.rabbitmq.publisher import RabbitMQMessagePublisher
from src.interfaces.messaging.kafka.client import IKafkaClient
from src.interfaces.messaging.rabbitmq.client import IAMQPClient


class _OrderPaidEvent(IntegrationEvent):
    destination: ClassVar[str] = "orders"
    routing_key: ClassVar[str] = "order.paid"

    order_id: str

    def partition_key(self) -> str | None:
        return self.order_id


_MESSAGE = OutgoingMessage(
    message_id="m-1",
    destination="users",
    routing_key="user.created",
    payload={"user_id": "u-1"},
    headers={"x-request-id": "req-1"},
    key="u-1",
)


async def test_rabbitmq_publish_message_maps_fields() -> None:
    rabbit = AsyncMock(spec=IAMQPClient)
    await RabbitMQMessagePublisher(rabbit=rabbit).publish_message(_MESSAGE)
    rabbit.publish.assert_awaited_once_with(
        exchange="users",
        routing_key="user.created",
        payload={"user_id": "u-1"},
        headers={"x-request-id": "req-1"},
        message_id="m-1",
    )


async def test_rabbitmq_publish_event_uses_event_routing() -> None:
    rabbit = AsyncMock(spec=IAMQPClient)
    event = _OrderPaidEvent(order_id="o-1")
    await RabbitMQMessagePublisher(rabbit=rabbit).publish(event)
    kwargs = rabbit.publish.await_args.kwargs
    assert kwargs["exchange"] == "orders"
    assert kwargs["routing_key"] == "order.paid"
    assert kwargs["message_id"] == event.event_id
    assert kwargs["payload"]["order_id"] == "o-1"


async def test_kafka_publish_message_maps_fields() -> None:
    kafka = AsyncMock(spec=IKafkaClient)
    await KafkaMessagePublisher(kafka=kafka).publish_message(_MESSAGE)
    kafka.publish.assert_awaited_once_with(
        topic="users",
        payload={"user_id": "u-1"},
        key="u-1",
        headers={"x-request-id": "req-1"},
        message_id="m-1",
    )


async def test_kafka_publish_event_uses_partition_key() -> None:
    kafka = AsyncMock(spec=IKafkaClient)
    await KafkaMessagePublisher(kafka=kafka).publish(_OrderPaidEvent(order_id="o-1"))
    kwargs = kafka.publish.await_args.kwargs
    assert kwargs["topic"] == "orders"
    assert kwargs["key"] == "o-1"
    assert kwargs["headers"]["x-event-type"] == "order.paid"
