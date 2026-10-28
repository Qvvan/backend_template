from __future__ import annotations

from src.core.logger import AppLogger
from src.interfaces.messaging.consumer import IConsumer
from src.interfaces.messaging.rabbitmq.client import IAMQPClient


class BackendConsumer(IConsumer):
    """Registers RabbitMQ queues and routes them to handlers — no logic here.

    Add a queue with `make consumer name=<event> broker=rabbitmq`, or by hand: a handler argument in
    `__init__` (wired in ConsumerContainer) and one `consume()` call in `start()`.
    """

    __slots__ = ("_logger", "_rabbit")

    def __init__(
        self,
        *,
        rabbit: IAMQPClient,
        logger: AppLogger,
        # scaffold:consumer-params
    ) -> None:
        self._rabbit = rabbit
        self._logger = logger
        # scaffold:consumer-assignments

    async def start(self) -> None:
        # scaffold:consumer-registrations
        self._logger.info("RabbitMQ consumers registered")

    async def stop(self) -> None:
        await self._rabbit.cancel_consumer()
        self._logger.info("RabbitMQ consumers stopped")
