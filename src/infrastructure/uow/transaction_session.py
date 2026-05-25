from __future__ import annotations

from src.interfaces.clients.db.query_executor import IQueryExecutor


class TransactionSession:
    __slots__ = ("_tx",)

    def __init__(self, tx: IQueryExecutor) -> None:
        self._tx = tx
