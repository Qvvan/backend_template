from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager

from src.interfaces.repositories.inbox_repository import IInboxRepository
from src.interfaces.repositories.outbox_repository import IOutboxRepository


class ITransactionSession(ABC):
    """Repositories bound to one open transaction. Add one property per aggregate the UoW must span."""

    # [if messaging]
    @property
    @abstractmethod
    def outbox(self) -> IOutboxRepository:
        raise NotImplementedError

    @property
    @abstractmethod
    def inbox(self) -> IInboxRepository:
        raise NotImplementedError

    # [endif]

    # scaffold:session-interface


class IUnitOfWork(ABC):
    @abstractmethod
    def begin(self) -> AbstractAsyncContextManager[ITransactionSession]:
        raise NotImplementedError
