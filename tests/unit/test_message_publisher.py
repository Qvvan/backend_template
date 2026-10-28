from __future__ import annotations

from unittest.mock import AsyncMock

from src.core.logger import AppLogger
from src.infrastructure.messaging.rabbitmq.publisher import MessagePublisher
from src.interfaces.messaging.rabbitmq.client import IAMQPClient


async def test_publish_delegates_to_rabbit_with_correct_args() -> None:
    mock_rabbit: IAMQPClient = AsyncMock(spec=IAMQPClient)
    publisher = MessagePublisher(rabbit=mock_rabbit, logger=AppLogger(level="DEBUG"))

    payload = {"user_id": "u-1", "email": "test@example.com"}
    await publisher.publish(exchange="users", routing_key="user.created", payload=payload)

    mock_rabbit.publish.assert_called_once_with(  # type: ignore[attr-defined]
        exchange="users",
        routing_key="user.created",
        payload=payload,
    )


async def test_publish_passes_empty_payload() -> None:
    mock_rabbit: IAMQPClient = AsyncMock(spec=IAMQPClient)
    publisher = MessagePublisher(rabbit=mock_rabbit, logger=AppLogger(level="DEBUG"))

    await publisher.publish(exchange="ex", routing_key="rk", payload={})

    mock_rabbit.publish.assert_called_once_with(  # type: ignore[attr-defined]
        exchange="ex",
        routing_key="rk",
        payload={},
    )
