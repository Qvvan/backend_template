from __future__ import annotations

from src.interfaces.clients.db.query_executor import IQueryExecutor


class TransactionSession:
    __slots__ = ("_tx",)

    def __init__(self, tx: IQueryExecutor) -> None:
        self._tx = tx

    @property
    def executor(self) -> IQueryExecutor:
        return self._tx

    # Pattern: add one @property per aggregate when UoW spans multiple tables.
    # Example:
    #   @property
    #   def orders(self) -> PostgresOrderRepository:
    #       return PostgresOrderRepository(self._tx)
