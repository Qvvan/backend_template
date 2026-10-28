from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar

import orjson
import pydantic
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, ConsumerRecord, TopicPartition

from src.core.events import MessageHeader
from src.core.logger import AppLogger
from src.interfaces.messaging.kafka.client import IKafkaClient

T = TypeVar("T", bound=pydantic.BaseModel)

_SASL_PROTOCOLS = frozenset({"SASL_PLAINTEXT", "SASL_SSL"})
_MAX_ERROR_HEADER_LENGTH = 1000


def dead_letter_topic_name(topic: str) -> str:
    return f"{topic}.dlq"


def _header(record: ConsumerRecord[bytes, bytes], name: str) -> str | None:
    for key, value in record.headers:
        if key == name:
            return value.decode()
    return None


class KafkaClient(IKafkaClient):
    """Kafka клиент для публикации и потребления сообщений.

    Consumers commit offsets manually after a message is handled (at-least-once). A handler error is
    retried in-process with exponential backoff; after the last retry — or right away if the payload is
    invalid — the message is sent to `<topic>.dlq` with the error in the `x-error` header.
    """

    __slots__ = (
        "_auto_offset_reset",
        "_bootstrap_servers",
        "_client_id",
        "_connect_lock",
        "_consumer_tasks",
        "_consumers",
        "_logger",
        "_max_retries",
        "_producer",
        "_retry_backoff",
        "_sasl_mechanism",
        "_sasl_password",
        "_sasl_username",
        "_security_protocol",
    )

    def __init__(
        self,
        logger: AppLogger,
        bootstrap_servers: str,
        client_id: str,
        security_protocol: str = "PLAINTEXT",
        sasl_mechanism: str | None = None,
        sasl_username: str | None = None,
        sasl_password: str | None = None,
        auto_offset_reset: str = "latest",
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._client_id = client_id
        self._security_protocol = security_protocol
        self._sasl_mechanism = sasl_mechanism
        self._sasl_username = sasl_username
        self._sasl_password = sasl_password
        self._auto_offset_reset = auto_offset_reset
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._logger = logger
        self._producer: AIOKafkaProducer | None = None
        self._consumers: dict[str, AIOKafkaConsumer] = {}
        self._consumer_tasks: dict[str, asyncio.Task[None]] = {}
        self._connect_lock = asyncio.Lock()

    def _build_sasl_kwargs(self) -> dict[str, Any]:
        if self._security_protocol not in _SASL_PROTOCOLS:
            return {}
        return {
            "sasl_mechanism": self._sasl_mechanism or "PLAIN",
            "sasl_plain_username": self._sasl_username,
            "sasl_plain_password": self._sasl_password,
        }

    async def connect(self) -> None:
        """Устанавливает соединение с Kafka (запускает producer)"""
        if self._producer is not None:
            return
        producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            client_id=self._client_id,
            security_protocol=self._security_protocol,
            acks="all",
            enable_idempotence=True,
            **self._build_sasl_kwargs(),
        )
        try:
            await producer.start()
        except Exception:
            await producer.stop()  # release the half-open client, otherwise it leaks
            raise
        self._producer = producer

    async def _ensure_producer(self) -> AIOKafkaProducer:
        if not self._producer:
            async with self._connect_lock:
                if not self._producer:
                    await self.connect()
        if self._producer is None:
            raise RuntimeError("Kafka producer not initialized after connect")
        return self._producer

    async def close(self) -> None:
        """Закрывает соединение и все consumer'ы"""
        await self.cancel_consumer()
        if self._producer:
            await self._producer.stop()
            self._producer = None

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
        headers: Mapping[str, str] | None = None,
        message_id: str | None = None,
    ) -> None:
        producer = await self._ensure_producer()
        all_headers = dict(headers or {})
        if message_id:
            all_headers[MessageHeader.MESSAGE_ID.value] = message_id
        await producer.send_and_wait(
            topic,
            value=orjson.dumps(payload),
            key=key.encode() if key else None,
            headers=[(name, value.encode()) for name, value in all_headers.items()] or None,
        )

    async def consume(
        self,
        topic: str,
        group_id: str,
        handler: Callable[[T], Awaitable[None]],
        model: type[T],
    ) -> None:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self._bootstrap_servers,
            client_id=self._client_id,
            group_id=group_id,
            security_protocol=self._security_protocol,
            enable_auto_commit=False,
            auto_offset_reset=self._auto_offset_reset,
            **self._build_sasl_kwargs(),
        )
        await consumer.start()
        consumer_key = f"{topic}:{group_id}"
        self._consumers[consumer_key] = consumer

        async def _run() -> None:
            async for record in consumer:
                token = AppLogger.bind_request_id(_header(record, MessageHeader.REQUEST_ID))
                try:
                    await self._process(record, handler, model)
                finally:
                    AppLogger.reset_request_id(token)
                await consumer.commit({TopicPartition(record.topic, record.partition): record.offset + 1})

        self._consumer_tasks[consumer_key] = asyncio.create_task(_run())

    async def _process(
        self,
        record: ConsumerRecord[bytes, bytes],
        handler: Callable[[T], Awaitable[None]],
        model: type[T],
    ) -> None:
        try:
            payload = model.model_validate_json(record.value or b"")
        except pydantic.ValidationError as exc:
            self._logger.error("Invalid message moved to DLQ", topic=record.topic, offset=record.offset)
            await self._dead_letter(record, exc, attempts=0)
            return

        for attempt in range(1, self._max_retries + 2):
            try:
                await handler(payload)
            except Exception as exc:
                if attempt > self._max_retries:
                    self._logger.error(
                        "Message handler failed, retries exhausted, moved to DLQ",
                        topic=record.topic,
                        offset=record.offset,
                        attempts=attempt,
                    )
                    await self._dead_letter(record, exc, attempts=attempt)
                    return
                delay = self._retry_backoff * 2 ** (attempt - 1)
                self._logger.warning(
                    "Message handler failed, retrying",
                    topic=record.topic,
                    offset=record.offset,
                    attempt=attempt,
                    delay_seconds=delay,
                    error=repr(exc),
                )
                await asyncio.sleep(delay)
            else:
                return

    async def _dead_letter(self, record: ConsumerRecord[bytes, bytes], exc: Exception, *, attempts: int) -> None:
        producer = await self._ensure_producer()
        headers = [(name, value) for name, value in record.headers if name != MessageHeader.ERROR]
        headers.append((MessageHeader.ERROR.value, repr(exc)[:_MAX_ERROR_HEADER_LENGTH].encode()))
        headers.append((MessageHeader.RETRY_COUNT.value, str(attempts).encode()))
        await producer.send_and_wait(
            dead_letter_topic_name(record.topic),
            value=record.value,
            key=record.key,
            headers=headers,
        )

    async def cancel_consumer(self) -> None:
        """Останавливает все запущенные consumer'ы"""
        for task in self._consumer_tasks.values():
            task.cancel()
        await asyncio.gather(*self._consumer_tasks.values(), return_exceptions=True)
        self._consumer_tasks.clear()

        for consumer in self._consumers.values():
            await consumer.stop()
        self._consumers.clear()

    async def health_check(self) -> bool:
        try:
            async with asyncio.timeout(5):
                producer = await self._ensure_producer()
                await producer.client.fetch_all_metadata()
            return True
        except Exception as e:
            self._logger.error("Kafka health check failed", error=e)
            return False
