import ssl
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any


class AMQPExchangeType(StrEnum):
    Direct: str = "direct"
    Fanout: str = "fanout"
    Topic: str = "topic"
    Headers: str = "headers"


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
    async def declare_exchange(self, name: str, exchange_type: str = "topic"):
        """Объявляет exchange"""
        raise NotImplementedError

    @abstractmethod
    async def declare_queue(self, name: str, exchange: str, routing_key: str, exchange_type: str = "topic") -> None:
        """Объявляет очередь и привязывает к exchange"""
        raise NotImplementedError

    @abstractmethod
    async def publish(self, exchange: str, routing_key: str, data: dict[str, Any]) -> None:
        """Публикует сообщение в exchange"""
        raise NotImplementedError

    @abstractmethod
    async def consume(self, queue_name: str, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def cancel_consumer(self) -> None:
        """Отменяет consumer по его тегу"""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """За двумя зайцами погонишься, ни одного не поймаешь, проверка не убежал ли наш заяц?"""
        raise NotImplementedError
