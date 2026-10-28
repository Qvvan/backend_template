from __future__ import annotations

from src.infrastructure.repository.postgresql.inbox_repository import PostgresInboxRepository
from src.infrastructure.repository.postgresql.outbox_repository import PostgresOutboxRepository
from src.interfaces.clients.db.query_executor import IQueryExecutor
from src.interfaces.clients.db.uow import ITransactionSession
from src.interfaces.repositories.inbox_repository import IInboxRepository
from src.interfaces.repositories.outbox_repository import IOutboxRepository


class TransactionSession(ITransactionSession):
    __slots__ = ("_tx",)

    def __init__(self, tx: IQueryExecutor) -> None:
        self._tx = tx

    @property
    def executor(self) -> IQueryExecutor:
        return self._tx

    @property
    def outbox(self) -> IOutboxRepository:
        return PostgresOutboxRepository(self._tx)

    @property
    def inbox(self) -> IInboxRepository:
        return PostgresInboxRepository(self._tx)

    # Pattern: add one @property per aggregate when UoW spans multiple tables
    # (declare it in ITransactionSession too).
    # Example:
    #   @property
    #   def orders(self) -> IOrderRepository:
    #       return PostgresOrderRepository(self._tx)
