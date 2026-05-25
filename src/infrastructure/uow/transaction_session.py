from src.interfaces.clients.db.query_executor import IQueryExecutor


class TransactionSession:
    """
    Lazy repository registry bound to a single open transaction.
    Each repo is created on first access and reused within the same session.
    """
    __slots__ = ("_tx",)

    def __init__(self, tx: IQueryExecutor) -> None:
        self._tx = tx
