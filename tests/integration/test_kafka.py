from __future__ import annotations

import asyncio
import uuid

import orjson
from aiokafka import AIOKafkaConsumer, ConsumerRecord
from pydantic import BaseModel

from src.core.events import MessageHeader
from src.core.logger import AppLogger
from src.infrastructure.messaging.kafka.client import KafkaClient, dead_letter_topic_name


class _Msg(BaseModel):
    value: str


def _topic() -> str:
    return f"test.{uuid.uuid4().hex[:8]}"


async def _read_one(bootstrap: str, topic: str, timeout: float = 20.0) -> ConsumerRecord[bytes, bytes]:
    consumer = AIOKafkaConsumer(topic, bootstrap_servers=bootstrap, auto_offset_reset="earliest")
    await consumer.start()
    try:
        return await asyncio.wait_for(consumer.getone(), timeout=timeout)
    finally:
        await consumer.stop()


def _headers(record: ConsumerRecord[bytes, bytes]) -> dict[str, str]:
    return {name: value.decode() for name, value in record.headers}


async def test_health_check(kafka_client: KafkaClient) -> None:
    assert await kafka_client.health_check() is True


async def test_publish_and_consume_with_headers(kafka_client: KafkaClient) -> None:
    topic = _topic()
    received: list[tuple[str, str | None]] = []
    done = asyncio.Event()

    async def handler(msg: _Msg) -> None:
        received.append((msg.value, AppLogger.get_request_id()))
        done.set()

    await kafka_client.publish(
        topic,
        {"value": "hello"},
        key="k-1",
        headers={MessageHeader.REQUEST_ID.value: "req-k"},
        message_id="m-1",
    )
    await kafka_client.consume(topic=topic, group_id="g1", handler=handler, model=_Msg)
    await asyncio.wait_for(done.wait(), timeout=20)

    assert received == [("hello", "req-k")]


async def test_failing_handler_is_retried_then_sent_to_dlq(kafka_client: KafkaClient, kafka_bootstrap: str) -> None:
    topic = _topic()
    calls = 0

    async def failing_handler(msg: _Msg) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("kafka handler failure")

    await kafka_client.publish(topic, {"value": "dead"}, key="k-dead")
    await kafka_client.consume(topic=topic, group_id="g2", handler=failing_handler, model=_Msg)

    dead = await _read_one(kafka_bootstrap, dead_letter_topic_name(topic))
    headers = _headers(dead)
    assert calls == 3  # 1 attempt + max_retries=2
    assert dead.key == b"k-dead"
    assert orjson.loads(dead.value or b"") == {"value": "dead"}
    assert "kafka handler failure" in headers[MessageHeader.ERROR]
    assert headers[MessageHeader.RETRY_COUNT] == "3"


async def test_invalid_payload_goes_to_dlq_and_consumer_continues(
    kafka_client: KafkaClient, kafka_bootstrap: str
) -> None:
    topic = _topic()
    received: list[str] = []
    done = asyncio.Event()

    async def handler(msg: _Msg) -> None:
        received.append(msg.value)
        done.set()

    await kafka_client.publish(topic, {"wrong_field": "oops"})
    await kafka_client.publish(topic, {"value": "after_bad"})
    await kafka_client.consume(topic=topic, group_id="g3", handler=handler, model=_Msg)

    await asyncio.wait_for(done.wait(), timeout=20)
    dead = await _read_one(kafka_bootstrap, dead_letter_topic_name(topic))
    assert received == ["after_bad"]
    assert b"wrong_field" in (dead.value or b"")


async def test_offsets_are_committed_after_processing(kafka_bootstrap: str, logger: AppLogger) -> None:
    """A second consumer in the same group does not get messages the first one already handled."""
    topic = _topic()
    first_client = KafkaClient(
        logger=logger, bootstrap_servers=kafka_bootstrap, client_id="t1", auto_offset_reset="earliest"
    )
    second_client = KafkaClient(
        logger=logger, bootstrap_servers=kafka_bootstrap, client_id="t2", auto_offset_reset="earliest"
    )
    seen_first: list[str] = []
    seen_second: list[str] = []
    first_done = asyncio.Event()

    async def first_handler(msg: _Msg) -> None:
        seen_first.append(msg.value)
        first_done.set()

    async def second_handler(msg: _Msg) -> None:
        seen_second.append(msg.value)

    try:
        await first_client.publish(topic, {"value": "once"})
        await first_client.consume(topic=topic, group_id="g-commit", handler=first_handler, model=_Msg)
        await asyncio.wait_for(first_done.wait(), timeout=20)
        await asyncio.sleep(0.5)  # let the commit land
        await first_client.close()

        await second_client.consume(topic=topic, group_id="g-commit", handler=second_handler, model=_Msg)
        await asyncio.sleep(3)
    finally:
        await first_client.close()
        await second_client.close()

    assert seen_first == ["once"]
    assert seen_second == []
