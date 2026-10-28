from __future__ import annotations

from src.interfaces.clients.db.query_executor import IQueryExecutor
from src.interfaces.repositories.inbox_repository import IInboxRepository


class PostgresInboxRepository(IInboxRepository):
    __slots__ = ("_executor",)

    def __init__(self, executor: IQueryExecutor) -> None:
        self._executor = executor

    async def register(self, message_id: str, consumer: str) -> bool:
        row = await self._executor.fetchrow(
            """
            INSERT INTO inbox (message_id, consumer) VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            RETURNING message_id
            """,
            message_id,
            consumer,
        )
        return row is not None
