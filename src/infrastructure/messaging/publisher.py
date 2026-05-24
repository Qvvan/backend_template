from typing import Any

from src.core.logger import AppLogger
from src.infrastructure.messaging.rabbitmq import RabbitMQClient
from src.interfaces.messaging.publisher import IMessagePublisher


class MessagePublisher(IMessagePublisher):
    """Общий publisher для всех событий"""
    __slots__ = ("_logger", "_rabbit")

    def __init__(self, rabbit: RabbitMQClient, logger: AppLogger):
        self._rabbit = rabbit
        self._logger = logger

    async def publish(self, exchange: str, routing_key: str, payload: dict[str, Any]) -> None:
        """Публикует событие об успешном расчете опроса"""
        await self._rabbit.publish(exchange=exchange, routing_key=routing_key, payload=payload)
