from __future__ import annotations

from src.core.logger import AppLogger
from src.interfaces.messaging.consumer import IConsumer
from src.interfaces.messaging.kafka.client import IKafkaClient


class KafkaBackendConsumer(IConsumer):
    """Registers Kafka topics and routes them to handlers — no logic here.

    Add a topic with `make consumer name=<event> broker=kafka`, or by hand: a handler argument in
    `__init__` (wired in ConsumerContainer) and one `consume()` call in `start()`.
    """

    __slots__ = ("_kafka", "_logger")

    def __init__(
        self,
        *,
        kafka: IKafkaClient,
        logger: AppLogger,
        # scaffold:consumer-params
    ) -> None:
        self._kafka = kafka
        self._logger = logger
        # scaffold:consumer-assignments

    async def start(self) -> None:
        # scaffold:consumer-registrations
        self._logger.info("Kafka consumers registered")

    async def stop(self) -> None:
        await self._kafka.cancel_consumer()
        self._logger.info("Kafka consumers stopped")
