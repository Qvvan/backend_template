from __future__ import annotations

import asyncio
import json
import ssl
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from urllib.parse import quote_plus

import aio_pika
from aio_pika import Message
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
    ConsumerTag,
)
from pydantic import BaseModel

from src.core.logger import AppLogger
from src.interfaces.messaging.client import IAMQPClient

T = TypeVar("T", bound=BaseModel)


class RabbitMQClient(IAMQPClient):
    """RabbitMQ клиент для публикации и потребления сообщений"""

    __slots__ = (
        "_cert_path",
        "_channel",
        "_connect_lock",
        "_connection",
        "_exchange_cache",
        "_logger",
        "_prefetch_count",
        "_queue_list",
        "_tls_enabled",
        "_url",
    )

    def __init__(
        self,
        logger: AppLogger,
        user: str,
        password: str,
        host: str,
        port: int,
        vhost: str,
        tls_enabled: bool,
        cert_path: str | None = None,
        prefetch_count: int = 10,
    ) -> None:
        protocol = "amqp"
        if tls_enabled:
            protocol = "amqps"
        self._url = f"{protocol}://{user}:{quote_plus(password)}@{host}:{port}/{vhost}"
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange_cache: dict[tuple[str, str], AbstractExchange] = {}
        self._queue_list: dict[AbstractQueue, ConsumerTag] = {}
        self._tls_enabled: bool = tls_enabled
        self._logger = logger
        self._cert_path: str | None = cert_path
        self._prefetch_count: int = prefetch_count
        self._connect_lock = asyncio.Lock()

    @property
    def _ch(self) -> AbstractChannel:
        if self._channel is None:
            raise RuntimeError("RabbitMQ channel not initialized — call connect() first")
        return self._channel

    async def connect(self) -> None:
        """Устанавливает соединение с RabbitMQ"""

        if self._tls_enabled:
            ssl_cnt = self._build_ssl_context()
            self._connection = await aio_pika.connect_robust(self._url, ssl_context=ssl_cnt)
        else:
            self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch_count)

    async def _ensure_connected(self) -> None:
        if not self._channel:
            async with self._connect_lock:
                if not self._channel:
                    await self.connect()
        assert self._channel is not None

    def _build_ssl_context(self) -> ssl.SSLContext:
        return ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=self._cert_path)

    async def close(self) -> None:
        """Закрывает соединение"""
        if self._channel:
            await self._channel.close()
            self._channel = None
        if self._connection:
            await self._connection.close()
            self._connection = None
        self._exchange_cache.clear()

    async def _declare_exchange(self, name: str, exchange_type: str = aio_pika.ExchangeType.TOPIC) -> AbstractExchange:
        await self._ensure_connected()
        cache_key = (name, exchange_type)
        ex = self._exchange_cache.get(cache_key)
        if not ex:
            ex = await self._ch.declare_exchange(name, aio_pika.ExchangeType(exchange_type), durable=True)
            self._exchange_cache[cache_key] = ex
        return ex

    async def _declare_queue(
        self, name: str, exchange: str, routing_key: str, exchange_type: str = aio_pika.ExchangeType.TOPIC
    ) -> AbstractQueue:
        await self._ensure_connected()
        ex = await self._declare_exchange(exchange, exchange_type=exchange_type)
        queue = await self._ch.declare_queue(name, durable=True)
        await queue.bind(ex, routing_key)
        return queue

    async def publish(self, exchange: str, routing_key: str, payload: dict[str, Any]) -> None:
        await self._ensure_connected()
        ex = await self._declare_exchange(exchange)
        message = Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await ex.publish(message, routing_key=routing_key)

    async def consume(
        self,
        queue_name: str,
        handler: Callable[[T], Awaitable[None]],
        model: type[T],
        exchange: str | None = None,
        routing_key: str | None = None,
        exchange_type: str = aio_pika.ExchangeType.TOPIC,
    ) -> None:
        await self._ensure_connected()

        if exchange and routing_key:
            queue = await self._declare_queue(queue_name, exchange, routing_key, exchange_type)
        else:
            queue = await self._ch.declare_queue(queue_name, durable=True, passive=False)

        async def on_message(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=False):
                try:
                    raw = json.loads(message.body.decode())
                    payload = model.model_validate(raw)
                    await handler(payload)
                except Exception as e:
                    self._logger.error("Message handler failed", error=e)
                    raise

        consumer_tag = await queue.consume(on_message)
        self._queue_list[queue] = consumer_tag

    async def cancel_consumer(self) -> None:
        for queue, consumer_tag in list(self._queue_list.items()):
            await queue.cancel(consumer_tag)
        self._queue_list.clear()

    async def health_check(self) -> bool:
        if self._connection is None or self._connection.is_closed:
            return False
        return not (self._channel is None or self._channel.is_closed)
