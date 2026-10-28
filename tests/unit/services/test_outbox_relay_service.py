from __future__ import annotations

import pytest

from src.core.logger import AppLogger
from src.domain.entities.messaging import OutgoingMessage
from src.services.outbox_relay_service import OutboxRelayService
from tests.fakes.messaging import FakeMessagePublisher
from tests.fakes.uow import FakeUnitOfWork


def _message(message_id: str) -> OutgoingMessage:
    return OutgoingMessage(message_id=message_id, destination="ex", routing_key="rk", payload={"n": message_id})


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


def _service(uow: FakeUnitOfWork, publisher: FakeMessagePublisher, batch_size: int = 10) -> OutboxRelayService:
    return OutboxRelayService(uow=uow, publisher=publisher, logger=AppLogger(level="DEBUG"), batch_size=batch_size)


async def test_relay_batch_publishes_and_deletes_messages(uow: FakeUnitOfWork) -> None:
    uow.outbox.messages = [_message("1"), _message("2")]
    publisher = FakeMessagePublisher()

    published = await _service(uow, publisher).relay_batch()

    assert published == 2
    assert [m.message_id for m in publisher.published] == ["1", "2"]
    assert uow.outbox.messages == []
    assert uow.commits == 1


async def test_relay_batch_respects_batch_size(uow: FakeUnitOfWork) -> None:
    uow.outbox.messages = [_message(str(i)) for i in range(5)]

    published = await _service(uow, FakeMessagePublisher(), batch_size=2).relay_batch()

    assert published == 2
    assert [m.message_id for m in uow.outbox.messages] == ["2", "3", "4"]


async def test_relay_batch_stops_at_first_failure_to_keep_order(uow: FakeUnitOfWork) -> None:
    uow.outbox.messages = [_message("1"), _message("2"), _message("3")]
    publisher = FakeMessagePublisher(fail_on=frozenset({"2"}))

    published = await _service(uow, publisher).relay_batch()

    assert published == 1
    assert [m.message_id for m in publisher.published] == ["1"]
    assert [m.message_id for m in uow.outbox.messages] == ["2", "3"]
    assert "broker unavailable" in uow.outbox.failures["2"][0]


async def test_relay_batch_with_empty_outbox_returns_zero(uow: FakeUnitOfWork) -> None:
    assert await _service(uow, FakeMessagePublisher()).relay_batch() == 0
