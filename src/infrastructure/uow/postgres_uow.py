from contextlib import asynccontextmanager

from src.infrastructure.repository.postgresql.client.connection import PostgresConnectionPool
from src.infrastructure.uow.transaction_session import TransactionSession


class PostgresUnitOfWork:
    """
    Generic transaction manager for PostgreSQL.
    begin() opens one connection, starts a transaction, and yields a
    TransactionSession with all repositories available lazily.
    Commits on clean exit, rolls back on any exception.
    """

    def __init__(self, pool: PostgresConnectionPool) -> None:
        self._pool = pool

    @asynccontextmanager
    async def begin(self):
        async with self._pool.transaction() as tx:
            yield TransactionSession(tx)
