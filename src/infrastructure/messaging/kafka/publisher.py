from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.core.logger import AppLogger
from src.interfaces.messaging.kafka.client import IKafkaClient
from src.interfaces.messaging.kafka.publisher import IKafkaPublisher


class KafkaMessagePublisher(IKafkaPublisher):
    """Общий publisher для всех Kafka-событий"""

    __slots__ = ("_kafka", "_logger")

    def __init__(self, kafka: IKafkaClient, logger: AppLogger) -> None:
        self._kafka = kafka
        self._logger = logger

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
        headers: Mapping[str, bytes] | None = None,
    ) -> None:
        """Публикует событие"""
        await self._kafka.publish(topic=topic, payload=payload, key=key, headers=headers)
