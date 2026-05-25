from __future__ import annotations

from abc import ABC, abstractmethod


class ICacheDB(ABC):
    @abstractmethod
    async def close(self) -> None:
        """Закрыть подключение."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Проверка жив ли"""
        raise NotImplementedError