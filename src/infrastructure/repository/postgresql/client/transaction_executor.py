from __future__ import annotations

from typing import Any, Mapping

import asyncpg

from src.interfaces.clients.db.query_executor import IQueryExecutor


class PostgresTransactionExecutor(IQueryExecutor):
    """IQueryExecutor, bound to a single connection inside an open transaction."""

    __slots__ = ("_conn",)

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        return await self._conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        return await self._conn.fetchrow(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        return await self._conn.execute(query, *args)
