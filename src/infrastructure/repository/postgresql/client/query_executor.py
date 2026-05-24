from typing import Any

from src.infrastructure.repository.postgresql.client.connection import PostgresConnectionPool
from src.interfaces.clients.db.query_executor import IQueryExecutor


class PostgresQueryExecutor(IQueryExecutor):
    __slots__ = ["_connection_pool"]

    def __init__(self, connection_pool: PostgresConnectionPool):
        self._connection_pool = connection_pool

    async def fetch(
            self,
            query: str,
            *args
    ) -> list:
        async with self._connection_pool.get_connection() as connection:
            return await connection.fetch(query, *args)

    async def fetchrow(
            self,
            query: str,
            *args
    ) -> Any | None:
        async with self._connection_pool.get_connection() as connection:
            return await connection.fetchrow(query, *args)

    async def execute(
            self,
            query: str,
            *args
    ) -> str:
        async with self._connection_pool.get_connection() as connection:
            return await connection.execute(query, *args)

