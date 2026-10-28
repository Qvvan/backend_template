from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class OutgoingMessage:
    """Broker-agnostic message ready to be published.

    `destination` is a RabbitMQ exchange or a Kafka topic; `routing_key` is a RabbitMQ routing key
    (for Kafka it travels in the `x-event-type` header); `key` is the Kafka partition key.
    """

    message_id: str
    destination: str
    routing_key: str
    payload: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)
    key: str | None = None
