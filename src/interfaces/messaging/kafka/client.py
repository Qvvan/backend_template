from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class IKafkaClient(ABC):
    """Kafka клиент для публикации и потребления сообщений"""

    @abstractmethod
    async def connect(self) -> None:
        """Устанавливает соединение с Kafka (запускает producer)"""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Закрывает соединение и все consumer'ы"""
        raise NotImplementedError

    @abstractmethod
    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
        headers: Mapping[str, str] | None = None,
        message_id: str | None = None,
    ) -> None:
        """Публикует сообщение в топик"""
        raise NotImplementedError

    @abstractmethod
    async def consume(
        self,
        topic: str,
        group_id: str,
        handler: Callable[[T], Awaitable[None]],
        model: type[T],
    ) -> None:
        """Запускает фоновое потребление топика consumer-группой.

        Offsets are committed only after a message is handled (at-least-once). A message that fails
        validation, or whose handler keeps failing after retries, is sent to `<topic>.dlq`.
        """
        raise NotImplementedError

    @abstractmethod
    async def cancel_consumer(self) -> None:
        """Останавливает все запущенные consumer'ы"""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Проверка жив ли брокер сообщений"""
        raise NotImplementedError
