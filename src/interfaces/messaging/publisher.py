from abc import ABC, abstractmethod
from typing import Any


class IMessagePublisher(ABC):
    """Общий publisher для всех событий"""

    @abstractmethod
    async def publish(self, exchange: str, routing_key: str, payload: dict[str, Any]) -> None:
        """Публикует событие"""
        raise NotImplementedError
