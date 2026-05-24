import json
import ssl
from collections.abc import Awaitable, Callable
from typing import Any
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

from src.core.logger import AppLogger
from src.interfaces.messaging.rabbitmq import IAMQPClient


class RabbitMQClient(IAMQPClient):
    """RabbitMQ клиент для публикации и потребления сообщений"""

    __slots__ = (
        "_channel",
        "_connection",
        "_exchange_cache",
        "_prefetch_count",
        "_queue_list",
        "_sert_path",
        "_ssl_context",
        "_logger",
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
        ssl_context: bool,
        sert_path: str | None = None,
    ) -> None:
        protocol = "amqp"
        if ssl_context:
            protocol = "amqps"
        self._url = f"{protocol}://{user}:{quote_plus(password)}@{host}:{port}/{vhost}"
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange_cache: dict[str, AbstractExchange] = {}
        self._queue_list: dict[AbstractQueue, ConsumerTag] = {}
        self._ssl_context: bool = ssl_context
        self._logger = logger
        self._sert_path: str | None = sert_path
        self._prefetch_count: int = 10

    async def connect(self) -> None:
        """Устанавливает соединение с RabbitMQ"""

        if self._ssl_context:
            ssl_cnt = self._build_ssl_context()
            self._connection = await aio_pika.connect_robust(self._url, ssl_context=ssl_cnt)
        else:
            self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch_count)

    def _build_ssl_context(self) -> ssl.SSLContext:
        return ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=self._sert_path)

    async def close(self) -> None:
        """Закрывает соединение"""
        if self._channel:
            await self._channel.close()
        if self._connection:
            await self._connection.close()

    async def declare_exchange(self, name: str, exchange_type: str = aio_pika.ExchangeType.TOPIC) -> AbstractExchange:
        if not self._channel:
            await self.connect()
        return await self._channel.declare_exchange(name, aio_pika.ExchangeType(exchange_type), durable=True)

    async def declare_queue(
            self, name: str, exchange: str, routing_key: str, exchange_type: str = aio_pika.ExchangeType.TOPIC
    ) -> None:
        if not self._channel:
            await self.connect()
        ex = await self.declare_exchange(exchange, exchange_type=exchange_type)
        queue = await self._channel.declare_queue(name, durable=True)
        await queue.bind(ex, routing_key)

    async def publish(self, exchange: str, routing_key: str, payload: dict[str, Any]) -> None:
        """Публикует сообщение в exchange"""
        if not self._channel:
            await self.connect()
        ex = self._exchange_cache.get(exchange)
        if not ex:
            ex = await self._channel.declare_exchange(exchange, aio_pika.ExchangeType.TOPIC, durable=True)
            self._exchange_cache[exchange] = ex
        message = Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await ex.publish(message, routing_key=routing_key)

    async def consume(self, queue_name: str, handler: Callable[[dict[str, Any]], Awaitable[None]]):
        """Запускает потребление сообщений из очереди и возвращает consumer_tag"""
        if not self._channel:
            await self.connect()

        queue = await self._channel.get_queue(queue_name)

        async def on_message(message: AbstractIncomingMessage) -> None:
            async with message.process():
                data = json.loads(message.body.decode())
                await handler(data)

        consumer_tag = await queue.consume(on_message)
        self._queue_list[queue] = consumer_tag

    async def cancel_consumer(self) -> None:
        for queue, consumer_tag in list(self._queue_list.items()):
            await queue.cancel(consumer_tag)

    async def health_check(self) -> bool:
        if self._connection is None or self._connection.is_closed:
            return False
        return not (self._channel is None or self._channel.is_closed)