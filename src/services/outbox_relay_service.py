from __future__ import annotations

from src.core.logger import AppLogger
from src.interfaces.clients.db.uow import IUnitOfWork
from src.interfaces.messaging.publisher import IMessagePublisher
from src.interfaces.services.outbox_relay_service import IOutboxRelayService


class OutboxRelayService(IOutboxRelayService):
    """Moves messages from the outbox table to the broker.

    Rows are locked with FOR UPDATE SKIP LOCKED, so several relay instances never publish the same row.
    Publishing stops at the first failure to keep the order of messages; the failed row stays in the
    outbox and is retried on the next batch. Delivery is at-least-once: consumers must be idempotent.
    """

    __slots__ = ("_batch_size", "_logger", "_publisher", "_uow")

    def __init__(self, uow: IUnitOfWork, publisher: IMessagePublisher, logger: AppLogger, batch_size: int) -> None:
        self._uow = uow
        self._publisher = publisher
        self._logger = logger
        self._batch_size = batch_size

    async def relay_batch(self) -> int:
        async with self._uow.begin() as session:
            messages = await session.outbox.fetch_pending(self._batch_size)
            published: list[str] = []
            for message in messages:
                try:
                    await self._publisher.publish_message(message)
                except Exception as exc:
                    self._logger.error(
                        "Outbox message publish failed",
                        message_id=message.message_id,
                        destination=message.destination,
                        routing_key=message.routing_key,
                    )
                    await session.outbox.mark_failed(message.message_id, repr(exc))
                    break
                published.append(message.message_id)
            await session.outbox.delete(published)
        return len(published)
