from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, TypeVar

from pydantic import BaseModel


class AMQPExchangeType(StrEnum):
    Direct = "direct"
    Fanout = "fanout"
    Topic = "topic"
    Headers = "headers"


T = TypeVar("T", bound=BaseModel)


class IAMQPClient(ABC):
    """RabbitMQ клиент для публикации и потребления сообщений"""

    @abstractmethod
    async def connect(self) -> None:
        """Устанавливает соединение с RabbitMQ"""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Закрывает соединение"""
        raise NotImplementedError

    @abstractmethod
    async def publish(self, exchange: str, routing_key: str, payload: dict[str, Any]) -> None:
        """Публикует сообщение в exchange"""
        raise NotImplementedError

    @abstractmethod
    async def consume(
        self,
        queue_name: str,
        handler: Callable[[T], Awaitable[None]],
        model: type[T],
        exchange: str | None = None,
        routing_key: str | None = None,
        exchange_type: str = AMQPExchangeType.Topic,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def cancel_consumer(self) -> None:
        """Отменяет consumer по его тегу"""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Проверка жив ли брокер сообщений"""
        raise NotImplementedError
