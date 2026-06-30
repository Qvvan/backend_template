from __future__ import annotations

from abc import ABC, abstractmethod


class ICacheRepository(ABC):
    """Интерфейс репозитория для работы с Redis."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Получить значение по ключу."""
        ...

    @abstractmethod
    async def set(
        self,
        key: str,
        value: str,
        expire: int | None = None,
    ) -> bool:
        """
        Установить значение по ключу.

        Args:
            key: Ключ
            value: Значение
            expire: Время жизни в секундах (None = без истечения)
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Удалить ключ."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Проверить существование ключа."""
        ...

    @abstractmethod
    async def expire(self, key: str, seconds: int) -> bool:
        """Установить время жизни ключа в секундах."""
        ...

    @abstractmethod
    async def ttl(self, key: str) -> int:
        """
        Получить оставшееся время жизни ключа в секундах.
        Возвращает -1 если ключ существует без TTL, -2 если ключ не существует.
        """
        ...

    @abstractmethod
    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        """Получить несколько значений по ключам."""
        ...

    @abstractmethod
    async def set_many(
        self,
        mapping: dict[str, str],
        expire: int | None = None,
    ) -> bool:
        """Установить несколько значений."""
        ...

    @abstractmethod
    async def delete_many(self, keys: list[str]) -> int:
        """Удалить несколько ключей. Возвращает количество удалённых ключей."""
        ...

    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int:
        """Увеличить значение на amount. Возвращает новое значение."""
        ...

    @abstractmethod
    async def decrement(self, key: str, amount: int = 1) -> int:
        """Уменьшить значение на amount. Возвращает новое значение."""
        ...

    @abstractmethod
    async def scan_keys(self, pattern: str = "*") -> list[str]:
        """Получить список ключей по паттерну через SCAN (non-blocking)."""
        ...
