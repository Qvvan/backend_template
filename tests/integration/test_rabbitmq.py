from __future__ import annotations

import asyncio
import uuid

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from pydantic import BaseModel

from src.core.events import MessageHeader
from src.core.logger import AppLogger
from src.infrastructure.messaging.rabbitmq.client import RabbitMQClient, dead_letter_queue_name
from src.interfaces.messaging.rabbitmq.client import AMQPExchangeType
from tests.integration.conftest import RABBIT_RETRY_DELAYS


class _Msg(BaseModel):
    value: str


def _unique_name(prefix: str) -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}"


async def test_health_check_after_connect(rabbit_client: RabbitMQClient) -> None:
    assert await rabbit_client.health_check() is True


async def test_health_check_before_connect(logger: AppLogger) -> None:
    client = RabbitMQClient(
        logger=logger,
        user="guest",
        password="guest",
        host="localhost",
        port=5672,
        vhost="/",
        tls_enabled=False,
    )
    assert await client.health_check() is False


async def test_publish_and_consume_message(rabbit_client: RabbitMQClient) -> None:
    exchange = _unique_name("test.ex")
    queue = _unique_name("test.q")
    routing_key = "test.event"

    received: list[_Msg] = []
    done = asyncio.Event()

    async def handler(msg: _Msg) -> None:
        received.append(msg)
        done.set()

    await rabbit_client.consume(
        queue_name=queue,
        handler=handler,
        model=_Msg,
        exchange=exchange,
        routing_key=routing_key,
        exchange_type=AMQPExchangeType.Topic,
    )
    await rabbit_client.publish(exchange, routing_key, {"value": "hello"})
    await asyncio.wait_for(done.wait(), timeout=5.0)

    assert len(received) == 1
    assert received[0].value == "hello"

    await rabbit_client.cancel_consumer()


async def test_cancel_consumer_clears_queue_list(rabbit_client: RabbitMQClient) -> None:
    async def noop(msg: _Msg) -> None:
        pass

    await rabbit_client.consume(
        queue_name=_unique_name("test.q"),
        handler=noop,
        model=_Msg,
    )
    assert len(rabbit_client._queue_list) == 1
    await rabbit_client.cancel_consumer()
    assert len(rabbit_client._queue_list) == 0


async def test_multiple_messages_in_order(rabbit_client: RabbitMQClient) -> None:
    exchange = _unique_name("test.ex")
    queue = _unique_name("test.q")
    routing_key = "test.order"

    received: list[str] = []
    expected_count = 3
    done = asyncio.Event()

    async def handler(msg: _Msg) -> None:
        received.append(msg.value)
        if len(received) == expected_count:
            done.set()

    await rabbit_client.consume(
        queue_name=queue,
        handler=handler,
        model=_Msg,
        exchange=exchange,
        routing_key=routing_key,
        exchange_type=AMQPExchangeType.Topic,
    )

    for i in range(expected_count):
        await rabbit_client.publish(exchange, routing_key, {"value": str(i)})

    await asyncio.wait_for(done.wait(), timeout=5.0)
    assert received == ["0", "1", "2"]

    await rabbit_client.cancel_consumer()


async def test_close_is_idempotent(rabbit_client: RabbitMQClient) -> None:
    await rabbit_client.close()
    await rabbit_client.close()


# ---------------------------------------------------------------------------
# Error-path / resilience tests: retries and dead-letter queue
# ---------------------------------------------------------------------------


async def _get_from_dlq(client: RabbitMQClient, queue: str, timeout: float = 5.0) -> AbstractIncomingMessage:
    dlq = await client._ch.declare_queue(dead_letter_queue_name(queue), durable=True, passive=True)
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        message = await dlq.get(fail=False)
        if message is not None:
            await message.ack()
            return message
        await asyncio.sleep(0.05)
    raise AssertionError(f"no message in {dead_letter_queue_name(queue)}")


async def _dlq_size(client: RabbitMQClient, queue: str) -> int:
    dlq = await client._ch.declare_queue(dead_letter_queue_name(queue), durable=True, passive=True)
    return dlq.declaration_result.message_count or 0


async def test_failing_handler_is_retried_then_moved_to_dlq(rabbit_client: RabbitMQClient) -> None:
    """Handler that always fails: 1 attempt + one per retry delay, then the message lands in <queue>.dlq."""
    exchange = _unique_name("test.ex")
    queue = _unique_name("test.q")
    routing_key = "test.fail"
    expected_calls = 1 + len(RABBIT_RETRY_DELAYS)

    call_count = 0

    async def failing_handler(msg: _Msg) -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("intentional failure")

    await rabbit_client.consume(
        queue_name=queue,
        handler=failing_handler,
        model=_Msg,
        exchange=exchange,
        routing_key=routing_key,
        exchange_type=AMQPExchangeType.Topic,
    )
    await rabbit_client.publish(exchange, routing_key, {"value": "dead"}, message_id="m-dead")

    dead = await _get_from_dlq(rabbit_client, queue)
    assert call_count == expected_calls
    assert dead.message_id == "m-dead"
    assert dead.headers[MessageHeader.RETRY_COUNT] == len(RABBIT_RETRY_DELAYS)
    assert "intentional failure" in str(dead.headers[MessageHeader.ERROR])
    await rabbit_client.cancel_consumer()


async def test_transient_failure_is_retried_and_succeeds(rabbit_client: RabbitMQClient) -> None:
    exchange = _unique_name("test.ex")
    queue = _unique_name("test.q")
    routing_key = "test.transient"

    attempts = 0
    done = asyncio.Event()

    async def flaky_handler(msg: _Msg) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary failure")
        done.set()

    await rabbit_client.consume(
        queue_name=queue,
        handler=flaky_handler,
        model=_Msg,
        exchange=exchange,
        routing_key=routing_key,
    )
    await rabbit_client.publish(exchange, routing_key, {"value": "retry_me"})
    await asyncio.wait_for(done.wait(), timeout=5.0)

    assert attempts == 2
    assert await _dlq_size(rabbit_client, queue) == 0
    await rabbit_client.cancel_consumer()


async def test_consume_invalid_json_goes_to_dlq_without_retries(rabbit_client: RabbitMQClient) -> None:
    """Невалидный JSON сразу уходит в DLQ (без ретраев), консьюмер жив и доставляет следующее сообщение."""
    exchange = _unique_name("test.ex")
    queue = _unique_name("test.q")
    routing_key = "test.badjson"

    received: list[_Msg] = []
    done = asyncio.Event()

    async def handler(msg: _Msg) -> None:
        received.append(msg)
        done.set()

    await rabbit_client.consume(
        queue_name=queue,
        handler=handler,
        model=_Msg,
        exchange=exchange,
        routing_key=routing_key,
        exchange_type=AMQPExchangeType.Topic,
    )

    # Публикуем сырые байты напрямую, минуя RabbitMQClient.publish() (который всегда даёт валидный JSON).
    ex = await rabbit_client._declare_exchange(exchange, AMQPExchangeType.Topic)
    await ex.publish(aio_pika.Message(body=b"{not valid json}"), routing_key=routing_key)
    await rabbit_client.publish(exchange, routing_key, {"value": "after_bad"})
    await asyncio.wait_for(done.wait(), timeout=5.0)

    dead = await _get_from_dlq(rabbit_client, queue)
    assert dead.body == b"{not valid json}"
    assert dead.headers[MessageHeader.RETRY_COUNT] == 0
    assert [m.value for m in received] == ["after_bad"]
    await rabbit_client.cancel_consumer()


async def test_consume_pydantic_validation_error_goes_to_dlq(rabbit_client: RabbitMQClient) -> None:
    """Валидный JSON, не прошедший pydantic-валидацию, уходит в DLQ; handler его не видит."""
    exchange = _unique_name("test.ex")
    queue = _unique_name("test.q")
    routing_key = "test.badschema"

    received: list[_Msg] = []
    done = asyncio.Event()

    async def handler(msg: _Msg) -> None:
        received.append(msg)
        done.set()

    await rabbit_client.consume(
        queue_name=queue,
        handler=handler,
        model=_Msg,
        exchange=exchange,
        routing_key=routing_key,
        exchange_type=AMQPExchangeType.Topic,
    )

    # Валидный JSON, но поле 'value' отсутствует — pydantic поднимет ValidationError.
    await rabbit_client.publish(exchange, routing_key, {"wrong_field": "oops"})
    await rabbit_client.publish(exchange, routing_key, {"value": "after_bad"})
    await asyncio.wait_for(done.wait(), timeout=5.0)

    dead = await _get_from_dlq(rabbit_client, queue)
    assert b"wrong_field" in dead.body
    assert "validation error" in str(dead.headers[MessageHeader.ERROR])
    assert [m.value for m in received] == ["after_bad"]
    await rabbit_client.cancel_consumer()


async def test_request_id_header_is_restored_in_handler_context(rabbit_client: RabbitMQClient) -> None:
    exchange = _unique_name("test.ex")
    queue = _unique_name("test.q")
    routing_key = "test.reqid"

    seen: list[str | None] = []
    done = asyncio.Event()

    async def handler(msg: _Msg) -> None:
        seen.append(AppLogger.get_request_id())
        done.set()

    await rabbit_client.consume(
        queue_name=queue,
        handler=handler,
        model=_Msg,
        exchange=exchange,
        routing_key=routing_key,
    )
    await rabbit_client.publish(
        exchange, routing_key, {"value": "x"}, headers={MessageHeader.REQUEST_ID.value: "req-from-api"}
    )
    await asyncio.wait_for(done.wait(), timeout=5.0)

    assert seen == ["req-from-api"]
    await rabbit_client.cancel_consumer()
