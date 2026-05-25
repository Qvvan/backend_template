from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from typing import Any


class IDBBase(ABC):
    """Базовый интерфейс — обязателен для всех БД."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...


class IDBConnectable(IDBBase, ABC):
    """Для БД с поддержкой соединений."""

    @abstractmethod
    def get_connection(self) -> AbstractAsyncContextManager[Any]: ...


class IDBTransactional(IDBConnectable, ABC):
    """Для БД с поддержкой транзакций."""

    @abstractmethod
    def transaction(self) -> AbstractAsyncContextManager[Any]: ...