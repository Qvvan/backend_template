from __future__ import annotations

import asyncio
import uuid

from pydantic import BaseModel

from src.core.logger import AppLogger
from src.infrastructure.messaging.rabbitmq import RabbitMQClient
from src.interfaces.messaging.client import AMQPExchangeType


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
