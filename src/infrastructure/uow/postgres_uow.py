from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from src.infrastructure.uow.transaction_session import TransactionSession
from src.interfaces.clients.db.connection import IDBTransactional
from src.interfaces.clients.db.uow import IUnitOfWork


class PostgresUnitOfWork(IUnitOfWork):
    __slots__ = ("_pool",)

    def __init__(self, pool: IDBTransactional) -> None:
        self._pool = pool

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[TransactionSession]:
        async with self._pool.transaction() as tx:
            yield TransactionSession(tx)
