from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class IFetch(ABC):
    @abstractmethod
    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        raise NotImplementedError


class IFetchRow(ABC):
    @abstractmethod
    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        raise NotImplementedError


class IExecutor(ABC):
    @abstractmethod
    async def execute(self, query: str, *args: Any) -> str:
        raise NotImplementedError


class IQueryExecutor(IFetch, IFetchRow, IExecutor, ABC):
    """Полный интерфейс для работы с БД"""
    ...
