from __future__ import annotations

from typing import ClassVar

from src.core.events import IntegrationEvent, MessageHeader
from src.core.logger import AppLogger


class _UserCreatedEvent(IntegrationEvent):
    destination: ClassVar[str] = "users"
    routing_key: ClassVar[str] = "user.created"

    user_id: str


class _KeyedEvent(_UserCreatedEvent):
    def partition_key(self) -> str | None:
        return self.user_id


def test_to_message_uses_class_routing() -> None:
    message = _UserCreatedEvent(user_id="u-1").to_message()
    assert message.destination == "users"
    assert message.routing_key == "user.created"


def test_to_message_payload_contains_fields_and_metadata() -> None:
    event = _UserCreatedEvent(user_id="u-1")
    message = event.to_message()
    assert message.message_id == event.event_id
    assert message.payload["user_id"] == "u-1"
    assert message.payload["event_id"] == event.event_id
    assert isinstance(message.payload["occurred_at"], str)  # JSON-ready


def test_to_message_sets_event_type_header() -> None:
    message = _UserCreatedEvent(user_id="u-1").to_message()
    assert message.headers[MessageHeader.EVENT_TYPE] == "user.created"


def test_to_message_carries_current_request_id() -> None:
    token = AppLogger.bind_request_id("req-7")
    try:
        message = _UserCreatedEvent(user_id="u-1").to_message()
    finally:
        AppLogger.reset_request_id(token)
    assert message.headers[MessageHeader.REQUEST_ID] == "req-7"


def test_to_message_without_request_id_has_no_header() -> None:
    message = _UserCreatedEvent(user_id="u-1").to_message()
    assert MessageHeader.REQUEST_ID not in message.headers


def test_partition_key_defaults_to_none_and_can_be_overridden() -> None:
    assert _UserCreatedEvent(user_id="u-1").to_message().key is None
    assert _KeyedEvent(user_id="u-1").to_message().key == "u-1"


def test_event_validates_its_own_payload() -> None:
    original = _UserCreatedEvent(user_id="u-1")
    restored = _UserCreatedEvent.model_validate(original.to_message().payload)
    assert restored == original


def test_each_event_gets_unique_id() -> None:
    assert _UserCreatedEvent(user_id="a").event_id != _UserCreatedEvent(user_id="a").event_id
