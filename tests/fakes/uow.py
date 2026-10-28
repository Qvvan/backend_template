from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from src.domain.entities.messaging import OutgoingMessage
from src.interfaces.clients.db.uow import ITransactionSession, IUnitOfWork
from src.interfaces.repositories.inbox_repository import IInboxRepository
from src.interfaces.repositories.outbox_repository import IOutboxRepository


class InMemoryOutboxRepository(IOutboxRepository):
    def __init__(self) -> None:
        self.messages: list[OutgoingMessage] = []
        self.failures: dict[str, list[str]] = {}

    async def add(self, message: OutgoingMessage) -> None:
        self.messages.append(message)

    async def fetch_pending(self, limit: int) -> list[OutgoingMessage]:
        return self.messages[:limit]

    async def delete(self, message_ids: list[str]) -> None:
        ids = set(message_ids)
        self.messages = [m for m in self.messages if m.message_id not in ids]

    async def mark_failed(self, message_id: str, error: str) -> None:
        self.failures.setdefault(message_id, []).append(error)


class InMemoryInboxRepository(IInboxRepository):
    def __init__(self) -> None:
        self.processed: set[tuple[str, str]] = set()

    async def register(self, message_id: str, consumer: str) -> bool:
        key = (message_id, consumer)
        if key in self.processed:
            return False
        self.processed.add(key)
        return True


class FakeTransactionSession(ITransactionSession):
    def __init__(self, outbox: InMemoryOutboxRepository, inbox: InMemoryInboxRepository) -> None:
        self._outbox = outbox
        self._inbox = inbox

    @property
    def outbox(self) -> IOutboxRepository:
        return self._outbox

    @property
    def inbox(self) -> IInboxRepository:
        return self._inbox


class FakeUnitOfWork(IUnitOfWork):
    """In-memory UoW: repositories are shared between transactions; counts commits and rollbacks.

    It does not undo changes on rollback — assert on `rollbacks` when a test needs atomicity.
    """

    def __init__(self) -> None:
        self.outbox = InMemoryOutboxRepository()
        self.inbox = InMemoryInboxRepository()
        self.commits = 0
        self.rollbacks = 0

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[ITransactionSession]:
        try:
            yield FakeTransactionSession(self.outbox, self.inbox)
        except BaseException:
            self.rollbacks += 1
            raise
        self.commits += 1
