from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from src.core.logger import AppLogger
from src.domain.entities.messaging import OutgoingMessage


class MessageHeader(StrEnum):
    """Headers the template puts on broker messages."""

    REQUEST_ID = "x-request-id"
    EVENT_TYPE = "x-event-type"
    MESSAGE_ID = "x-message-id"
    RETRY_COUNT = "x-retry-count"
    ERROR = "x-error"


class IntegrationEvent(BaseModel):
    """Base class for events published to a message broker.

    A subclass is the contract shared by the publisher and the consumer:

        class UserCreatedEvent(IntegrationEvent):
            destination: ClassVar[str] = "users"         # RabbitMQ exchange / Kafka topic
            routing_key: ClassVar[str] = "user.created"  # RabbitMQ routing key / Kafka event type

            user_id: str
            email: str

    Publish it with `IMessagePublisher.publish(event)` or atomically with a DB change via
    `session.outbox.add(event.to_message())` inside `IUnitOfWork.begin()`; consume it by passing the
    class as `model=` to `consume()`.
    """

    model_config = ConfigDict(frozen=True)

    destination: ClassVar[str]
    routing_key: ClassVar[str]

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def partition_key(self) -> str | None:
        """Kafka message key: events with the same key keep their order. None means any partition."""
        return None

    def to_message(self) -> OutgoingMessage:
        """Serialize the event; the current request id is carried along in headers."""
        headers = {MessageHeader.EVENT_TYPE.value: self.routing_key}
        request_id = AppLogger.get_request_id()
        if request_id:
            headers[MessageHeader.REQUEST_ID.value] = request_id
        return OutgoingMessage(
            message_id=self.event_id,
            destination=self.destination,
            routing_key=self.routing_key,
            payload=self.model_dump(mode="json"),
            headers=headers,
            key=self.partition_key(),
        )
