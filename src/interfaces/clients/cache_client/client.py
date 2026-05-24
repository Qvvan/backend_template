from abc import ABC, abstractmethod
from typing import Any


class ICacheDB(ABC):

    @property
    @abstractmethod
    def client(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Закрыть подключение."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Проверка жив ли"""
        raise NotImplementedError