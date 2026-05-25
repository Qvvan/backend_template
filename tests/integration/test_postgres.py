from __future__ import annotations

import asyncio

import pytest

from src.infrastructure.repository.postgresql.client.connection import PostgresConnectionPool
from src.infrastructure.repository.postgresql.client.query_executor import PostgresQueryExecutor
from src.infrastructure.uow.postgres_uow import PostgresUnitOfWork


async def test_pool_health_check(pg_pool: PostgresConnectionPool) -> None:
    assert await pg_pool.health_check() is True


async def test_executor_fetchrow_returns_row(pg_executor: PostgresQueryExecutor) -> None:
    row = await pg_executor.fetchrow("SELECT 1 AS num, 'hello' AS txt")
    assert row is not None
    assert row["num"] == 1
    assert row["txt"] == "hello"


async def test_executor_fetchrow_returns_none_when_no_match(pg_executor: PostgresQueryExecutor) -> None:
    row = await pg_executor.fetchrow("SELECT 1 WHERE false")
    assert row is None


async def test_executor_fetch_returns_multiple_rows(pg_executor: PostgresQueryExecutor) -> None:
    rows = await pg_executor.fetch("SELECT generate_series(1, 3) AS n")
    assert len(rows) == 3
    assert [r["n"] for r in rows] == [1, 2, 3]


async def test_executor_fetch_empty_result(pg_executor: PostgresQueryExecutor) -> None:
    rows = await pg_executor.fetch("SELECT 1 WHERE false")
    assert rows == []


async def test_executor_parameterized_query(pg_executor: PostgresQueryExecutor) -> None:
    row = await pg_executor.fetchrow("SELECT $1::int AS n, $2::text AS s", 42, "world")
    assert row is not None
    assert row["n"] == 42
    assert row["s"] == "world"


async def test_executor_execute_returns_status_string(pg_executor: PostgresQueryExecutor) -> None:
    result = await pg_executor.execute("SELECT 1")
    assert isinstance(result, str)


async def test_transaction_commit(pg_pool: PostgresConnectionPool) -> None:
    async with pg_pool.transaction() as tx:
        row = await tx.fetchrow("SELECT $1::text AS val", "in_tx")
    assert row is not None
    assert row["val"] == "in_tx"


async def test_transaction_rollback_on_exception(pg_pool: PostgresConnectionPool) -> None:
    with pytest.raises(RuntimeError, match="forced"):
        async with pg_pool.transaction() as tx:
            row = await tx.fetchrow("SELECT 1 AS n")
            assert row is not None
            raise RuntimeError("forced rollback")


async def test_uow_begin_yields_transaction_session(pg_uow: PostgresUnitOfWork) -> None:
    async with pg_uow.begin() as session:
        row = await session._tx.fetchrow("SELECT 42 AS answer")
    assert row is not None
    assert row["answer"] == 42


async def test_pool_can_handle_concurrent_queries(pg_executor: PostgresQueryExecutor) -> None:
    results = await asyncio.gather(
        pg_executor.fetchrow("SELECT $1::int AS n", 1),
        pg_executor.fetchrow("SELECT $1::int AS n", 2),
        pg_executor.fetchrow("SELECT $1::int AS n", 3),
    )
    values = [r["n"] for r in results if r is not None]
    assert sorted(values) == [1, 2, 3]
