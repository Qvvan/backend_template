from __future__ import annotations

from functools import cached_property

from src.core.container.infrastructure import InfrastructureContainer
from src.core.container.services import ServiceContainer
from src.core.logger import AppLogger
from src.infrastructure.messaging.kafka.consumer import KafkaBackendConsumer
from src.infrastructure.messaging.rabbitmq.consumer import BackendConsumer
from src.interfaces.messaging.consumer import IConsumer


class ConsumerContainer:
    """Message consumers with their handlers. Started only by the consumer process (src/entrypoints/consumer.py)."""

    def __init__(self, logger: AppLogger, infra: InfrastructureContainer, services: ServiceContainer) -> None:
        self._logger = logger
        self._infra = infra
        self._services = services

    @cached_property
    def rabbitmq(self) -> IConsumer:
        return BackendConsumer(
            rabbit=self._infra.rabbitmq,
            logger=self._logger,
            # scaffold:rabbitmq-handlers
        )

    @cached_property
    def kafka(self) -> IConsumer:
        return KafkaBackendConsumer(
            kafka=self._infra.kafka,
            logger=self._logger,
            # scaffold:kafka-handlers
        )

    @property
    def all(self) -> list[IConsumer]:
        return [self.rabbitmq, self.kafka]

    async def start(self) -> None:
        for consumer in self.all:
            await consumer.start()

    async def stop(self) -> None:
        if "rabbitmq" in self.__dict__:
            await self.rabbitmq.stop()
        if "kafka" in self.__dict__:
            await self.kafka.stop()
