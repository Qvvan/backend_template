from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.domain.entities.messaging import OutgoingMessage
from src.interfaces.clients.db.query_executor import IQueryExecutor
from src.interfaces.repositories.outbox_repository import IOutboxRepository


class PostgresOutboxRepository(IOutboxRepository):
    __slots__ = ("_executor",)

    def __init__(self, executor: IQueryExecutor) -> None:
        self._executor = executor

    async def add(self, message: OutgoingMessage) -> None:
        await self._executor.execute(
            """
            INSERT INTO outbox (id, destination, routing_key, message_key, payload, headers)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            message.message_id,
            message.destination,
            message.routing_key,
            message.key,
            message.payload,
            message.headers,
        )

    async def fetch_pending(self, limit: int) -> list[OutgoingMessage]:
        rows = await self._executor.fetch(
            """
            SELECT id, destination, routing_key, message_key, payload, headers
            FROM outbox
            ORDER BY created_at
            LIMIT $1
            FOR UPDATE SKIP LOCKED
            """,
            limit,
        )
        return [self._map(row) for row in rows]

    async def delete(self, message_ids: list[str]) -> None:
        if not message_ids:
            return
        await self._executor.execute("DELETE FROM outbox WHERE id = ANY($1::text[])", message_ids)

    async def mark_failed(self, message_id: str, error: str) -> None:
        await self._executor.execute(
            "UPDATE outbox SET attempts = attempts + 1, last_error = $2 WHERE id = $1",
            message_id,
            error,
        )

    @staticmethod
    def _map(row: Mapping[str, Any]) -> OutgoingMessage:
        return OutgoingMessage(
            message_id=row["id"],
            destination=row["destination"],
            routing_key=row["routing_key"],
            key=row["message_key"],
            payload=row["payload"],
            headers=row["headers"],
        )
