from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class IKafkaPublisher(ABC):
    """Общий publisher для всех Kafka-событий"""

    @abstractmethod
    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
        headers: Mapping[str, bytes] | None = None,
    ) -> None:
        """Публикует событие"""
        raise NotImplementedError
