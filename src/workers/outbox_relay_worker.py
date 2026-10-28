from __future__ import annotations

from src.core.logger import AppLogger
from src.interfaces.services.outbox_relay_service import IOutboxRelayService
from src.workers.periodic import PeriodicWorker


class OutboxRelayWorker(PeriodicWorker):
    """Publishes pending outbox messages every `interval` seconds."""

    __slots__ = ("_service",)

    def __init__(self, service: IOutboxRelayService, logger: AppLogger, interval: float) -> None:
        super().__init__(logger=logger, interval=interval)
        self._service = service

    @property
    def name(self) -> str:
        return "outbox_relay"

    async def tick(self) -> None:
        await self._service.relay_batch()
