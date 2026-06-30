from __future__ import annotations

import asyncio

from src.core.logger import AppLogger
from src.interfaces.messaging.consumer import IConsumer
from src.interfaces.messaging.kafka.client import IKafkaClient


class KafkaBackendConsumer(IConsumer):
    __slots__ = ("_kafka", "_logger", "_stop_event")

    def __init__(
        self,
        *,
        kafka: IKafkaClient,
        logger: AppLogger,
        stop: asyncio.Event,
    ) -> None:
        self._kafka = kafka
        self._logger = logger
        self._stop_event: asyncio.Event = stop

    async def start(self) -> None:
        await self.register_consumers()
        await self._stop_event.wait()
        self._logger.info("Stop signal received, cancelling consumers...")
        await self._kafka.cancel_consumer()

    async def register_consumers(self) -> None:
        """Настройка всех consumers для обработки сообщений"""

        self._logger.info("Kafka consumer started")
