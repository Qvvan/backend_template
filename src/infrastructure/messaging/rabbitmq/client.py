from __future__ import annotations

import asyncio
import ssl
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar
from urllib.parse import quote_plus

import aio_pika
import orjson
import pydantic
from aio_pika import Message
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
    ConsumerTag,
)

from src.core.events import MessageHeader
from src.core.logger import AppLogger
from src.interfaces.messaging.rabbitmq.client import IAMQPClient

T = TypeVar("T", bound=pydantic.BaseModel)

_JSON_CONTENT_TYPE = "application/json"
_MAX_ERROR_HEADER_LENGTH = 1000


def dead_letter_queue_name(queue_name: str) -> str:
    return f"{queue_name}.dlq"


def retry_queue_name(queue_name: str, attempt: int) -> str:
    return f"{queue_name}.retry.{attempt}"


class RabbitMQClient(IAMQPClient):
    """RabbitMQ клиент для публикации и потребления сообщений.

    Failed messages are not lost: a handler error re-publishes the message to `<queue>.retry.<n>`
    (a queue with TTL that dead-letters back into `<queue>`), and after the last retry — or right away
    if the payload is invalid — the message is moved to `<queue>.dlq` with the error in `x-error`.
    """

    __slots__ = (
        "_cert_path",
        "_channel",
        "_connect_lock",
        "_connection",
        "_exchange_cache",
        "_logger",
        "_prefetch_count",
        "_queue_list",
        "_retry_delays",
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
        retry_delays: tuple[float, ...] = (1.0, 10.0, 60.0),
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
        self._retry_delays = retry_delays
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
        # publisher_confirms=True (default): publish() returns only after the broker accepted the message
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch_count)

    async def _ensure_connected(self) -> None:
        if not self._channel:
            async with self._connect_lock:
                if not self._channel:
                    await self.connect()
        if self._channel is None:
            raise RuntimeError("RabbitMQ channel not initialized after connect")

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

    async def _declare_consumer_queues(self, queue_name: str) -> AbstractQueue:
        """Main queue plus its retry queues and dead-letter queue."""
        queue = await self._ch.declare_queue(queue_name, durable=True)
        await self._ch.declare_queue(dead_letter_queue_name(queue_name), durable=True)
        for attempt, delay in enumerate(self._retry_delays, start=1):
            await self._ch.declare_queue(
                retry_queue_name(queue_name, attempt),
                durable=True,
                arguments={
                    "x-message-ttl": int(delay * 1000),
                    # On expiry the message goes back to the main queue via the default exchange
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": queue_name,
                },
            )
        return queue

    async def publish(
        self,
        exchange: str,
        routing_key: str,
        payload: dict[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
        message_id: str | None = None,
    ) -> None:
        await self._ensure_connected()
        ex = await self._declare_exchange(exchange)
        message = Message(
            body=orjson.dumps(payload),
            headers=dict(headers or {}),
            message_id=message_id,
            content_type=_JSON_CONTENT_TYPE,
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

        queue = await self._declare_consumer_queues(queue_name)
        if exchange and routing_key:
            ex = await self._declare_exchange(exchange, exchange_type=exchange_type)
            await queue.bind(ex, routing_key)

        async def on_message(message: AbstractIncomingMessage) -> None:
            request_id = message.headers.get(MessageHeader.REQUEST_ID)
            token = AppLogger.bind_request_id(request_id if isinstance(request_id, str) else None)
            try:
                await self._process(message, queue_name, handler, model)
            finally:
                AppLogger.reset_request_id(token)

        consumer_tag = await queue.consume(on_message)
        self._queue_list[queue] = consumer_tag

    async def _process(
        self,
        message: AbstractIncomingMessage,
        queue_name: str,
        handler: Callable[[T], Awaitable[None]],
        model: type[T],
    ) -> None:
        try:
            payload = model.model_validate_json(message.body)
        except pydantic.ValidationError as exc:
            self._logger.error("Invalid message moved to DLQ", queue=queue_name, message_id=message.message_id)
            await self._dead_letter(message, queue_name, exc)
            return

        try:
            await handler(payload)
        except Exception as exc:
            await self._retry_or_dead_letter(message, queue_name, exc)
            return

        await message.ack()

    async def _retry_or_dead_letter(self, message: AbstractIncomingMessage, queue_name: str, exc: Exception) -> None:
        retry_count = message.headers.get(MessageHeader.RETRY_COUNT, 0)
        attempt = (retry_count if isinstance(retry_count, int) else 0) + 1
        if attempt > len(self._retry_delays):
            self._logger.error(
                "Message handler failed, retries exhausted, moved to DLQ",
                queue=queue_name,
                message_id=message.message_id,
                attempts=attempt,
            )
            await self._dead_letter(message, queue_name, exc)
            return

        self._logger.warning(
            "Message handler failed, retry scheduled",
            queue=queue_name,
            message_id=message.message_id,
            attempt=attempt,
            delay_seconds=self._retry_delays[attempt - 1],
            error=repr(exc),
        )
        await self._republish(message, retry_queue_name(queue_name, attempt), exc, retry_count=attempt)

    async def _dead_letter(self, message: AbstractIncomingMessage, queue_name: str, exc: Exception) -> None:
        retry_count = message.headers.get(MessageHeader.RETRY_COUNT, 0)
        await self._republish(
            message,
            dead_letter_queue_name(queue_name),
            exc,
            retry_count=retry_count if isinstance(retry_count, int) else 0,
        )

    async def _republish(
        self,
        message: AbstractIncomingMessage,
        target_queue: str,
        exc: Exception,
        *,
        retry_count: int,
    ) -> None:
        """Copy the message into `target_queue` (via the default exchange), then ack the original."""
        headers = dict(message.headers)
        headers[MessageHeader.RETRY_COUNT.value] = retry_count
        headers[MessageHeader.ERROR.value] = repr(exc)[:_MAX_ERROR_HEADER_LENGTH]
        copy = Message(
            body=message.body,
            headers=headers,
            message_id=message.message_id,
            content_type=message.content_type,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._ch.default_exchange.publish(copy, routing_key=target_queue)
        await message.ack()

    async def cancel_consumer(self) -> None:
        for queue, consumer_tag in list(self._queue_list.items()):
            await queue.cancel(consumer_tag)
        self._queue_list.clear()

    async def health_check(self) -> bool:
        try:
            async with asyncio.timeout(5):
                await self._ensure_connected()
            return not (self._channel is None or self._channel.is_closed)
        except Exception as e:
            self._logger.error("RabbitMQ health check failed", error=e)
            return False
