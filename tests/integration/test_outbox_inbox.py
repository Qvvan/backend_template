from __future__ import annotations

import uuid

from src.core.logger import AppLogger
from src.domain.entities.messaging import OutgoingMessage
from src.infrastructure.repository.postgresql.client.query_executor import PostgresQueryExecutor
from src.infrastructure.repository.postgresql.client.transaction_executor import PostgresTransactionExecutor
from src.infrastructure.repository.postgresql.inbox_repository import PostgresInboxRepository
from src.infrastructure.repository.postgresql.outbox_repository import PostgresOutboxRepository
from src.infrastructure.uow.postgres_uow import PostgresUnitOfWork
from src.services.outbox_relay_service import OutboxRelayService
from tests.fakes.messaging import FakeMessagePublisher


def _message(**overrides: object) -> OutgoingMessage:
    values: dict[str, object] = {
        "message_id": str(uuid.uuid4()),
        "destination": "users",
        "routing_key": "user.created",
        "payload": {"user_id": "u-1", "tags": ["a", "b"]},
        "headers": {"x-request-id": "req-1"},
        "key": "u-1",
    }
    values.update(overrides)
    return OutgoingMessage(**values)  # type: ignore[arg-type]  # test helper with loose overrides


# ── outbox repository ─────────────────────────────────────────────────────────


async def test_outbox_add_and_fetch_round_trip(db_executor: PostgresTransactionExecutor) -> None:
    repo = PostgresOutboxRepository(db_executor)
    message = _message()
    await repo.add(message)

    assert await repo.fetch_pending(10) == [message]


async def test_outbox_fetch_pending_returns_oldest_first_with_limit(db_executor: PostgresTransactionExecutor) -> None:
    repo = PostgresOutboxRepository(db_executor)
    first, second, third = _message(), _message(), _message()
    for message in (first, second, third):
        await repo.add(message)
        await db_executor.execute("SELECT pg_sleep(0.01)")  # distinct created_at

    pending = await repo.fetch_pending(2)

    assert [m.message_id for m in pending] == [first.message_id, second.message_id]


async def test_outbox_delete_and_mark_failed(db_executor: PostgresTransactionExecutor) -> None:
    repo = PostgresOutboxRepository(db_executor)
    kept, deleted = _message(), _message()
    await repo.add(kept)
    await repo.add(deleted)

    await repo.delete([deleted.message_id])
    await repo.mark_failed(kept.message_id, "broker down")

    row = await db_executor.fetchrow("SELECT attempts, last_error FROM outbox WHERE id = $1", kept.message_id)
    assert [m.message_id for m in await repo.fetch_pending(10)] == [kept.message_id]
    assert row is not None
    assert row["attempts"] == 1
    assert row["last_error"] == "broker down"


async def test_outbox_rows_locked_by_one_transaction_are_skipped_by_another(pg_uow: PostgresUnitOfWork) -> None:
    message = _message()
    async with pg_uow.begin() as session:
        await session.outbox.add(message)

    try:
        async with pg_uow.begin() as first:
            locked = await first.outbox.fetch_pending(10)
            async with pg_uow.begin() as second:
                assert message.message_id not in [m.message_id for m in await second.outbox.fetch_pending(10)]
            assert message.message_id in [m.message_id for m in locked]
    finally:
        async with pg_uow.begin() as session:
            await session.outbox.delete([message.message_id])


# ── outbox relay end-to-end with real Postgres ────────────────────────────────


async def test_outbox_written_in_rolled_back_transaction_is_not_published(
    pg_uow: PostgresUnitOfWork, pg_executor: PostgresQueryExecutor
) -> None:
    message = _message()
    try:
        async with pg_uow.begin() as session:
            await session.outbox.add(message)
            raise RuntimeError("business operation failed")
    except RuntimeError:
        pass

    row = await pg_executor.fetchrow("SELECT 1 FROM outbox WHERE id = $1", message.message_id)
    assert row is None


async def test_relay_publishes_committed_outbox_messages(pg_uow: PostgresUnitOfWork, logger: AppLogger) -> None:
    message = _message()
    async with pg_uow.begin() as session:
        await session.outbox.add(message)

    publisher = FakeMessagePublisher()
    relay = OutboxRelayService(uow=pg_uow, publisher=publisher, logger=logger, batch_size=100)
    await relay.relay_batch()

    assert message in publisher.published
    async with pg_uow.begin() as session:
        assert message.message_id not in [m.message_id for m in await session.outbox.fetch_pending(100)]


# ── inbox repository ──────────────────────────────────────────────────────────


async def test_inbox_register_is_true_once_per_consumer(db_executor: PostgresTransactionExecutor) -> None:
    repo = PostgresInboxRepository(db_executor)
    message_id = str(uuid.uuid4())

    assert await repo.register(message_id, "billing") is True
    assert await repo.register(message_id, "billing") is False
    assert await repo.register(message_id, "notifications") is True
