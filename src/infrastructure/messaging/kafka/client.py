from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import BaseModel

from src.core.logger import AppLogger
from src.interfaces.messaging.kafka.client import IKafkaClient

T = TypeVar("T", bound=BaseModel)

_SASL_PROTOCOLS = frozenset({"SASL_PLAINTEXT", "SASL_SSL"})


class KafkaClient(IKafkaClient):
    """Kafka клиент для публикации и потребления сообщений"""

    __slots__ = (
        "_auto_offset_reset",
        "_bootstrap_servers",
        "_client_id",
        "_connect_lock",
        "_consumer_tasks",
        "_consumers",
        "_enable_auto_commit",
        "_logger",
        "_producer",
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
        enable_auto_commit: bool = True,
        auto_offset_reset: str = "latest",
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._client_id = client_id
        self._security_protocol = security_protocol
        self._sasl_mechanism = sasl_mechanism
        self._sasl_username = sasl_username
        self._sasl_password = sasl_password
        self._enable_auto_commit = enable_auto_commit
        self._auto_offset_reset = auto_offset_reset
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
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            client_id=self._client_id,
            security_protocol=self._security_protocol,
            **self._build_sasl_kwargs(),
        )
        await self._producer.start()

    async def _ensure_connected(self) -> None:
        if not self._producer:
            async with self._connect_lock:
                if not self._producer:
                    await self.connect()
        if self._producer is None:
            raise RuntimeError("Kafka producer not initialized after connect")

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
        headers: Mapping[str, bytes] | None = None,
    ) -> None:
        await self._ensure_connected()
        if self._producer is None:
            raise RuntimeError("Kafka producer not initialized")
        await self._producer.send_and_wait(
            topic,
            value=json.dumps(payload).encode(),
            key=key.encode() if key else None,
            headers=list(headers.items()) if headers else None,
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
            enable_auto_commit=self._enable_auto_commit,
            auto_offset_reset=self._auto_offset_reset,
            **self._build_sasl_kwargs(),
        )
        await consumer.start()
        self._consumers[topic] = consumer

        async def _run() -> None:
            async for message in consumer:
                if message.value is None:
                    continue
                try:
                    raw = json.loads(message.value.decode())
                    payload = model.model_validate(raw)
                    await handler(payload)
                except Exception as e:
                    self._logger.error("Message handler failed", error=e, topic=topic)

        self._consumer_tasks[topic] = asyncio.create_task(_run())

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
                await self._ensure_connected()
                if self._producer is not None:
                    await self._producer.client.fetch_all_metadata()
            return True
        except Exception as e:
            self._logger.error("Kafka health check failed", error=e)
            return False
