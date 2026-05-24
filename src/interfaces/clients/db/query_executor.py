from abc import ABC, abstractmethod
from typing import Any


class IFetch(ABC):
    @abstractmethod
    async def fetch(self, query, *args) -> list:
        raise NotImplementedError


class IFetchRow(ABC):
    @abstractmethod
    async def fetchrow(self, query: str, *args) -> Any | None:
        raise NotImplementedError


class IExecutor(ABC):
    @abstractmethod
    async def execute(self, query: str, *args) -> str:
        raise NotImplementedError


class IQueryExecutor(IFetch, IFetchRow, IExecutor, ABC):
    """Полный интерфейс для работы с БД"""
    ...
