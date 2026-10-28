from __future__ import annotations

from functools import cached_property

from src.core.config import Config
from src.core.container.infrastructure import InfrastructureContainer
from src.core.container.repositories import RepositoryContainer
from src.core.logger import AppLogger
from src.interfaces.services.health_service import IHealthService
from src.interfaces.services.outbox_relay_service import IOutboxRelayService
from src.services.health_service import HealthService
from src.services.outbox_relay_service import OutboxRelayService


class ServiceContainer:
    """Ленивая инициализация сервисов."""

    def __init__(
        self,
        config: Config,
        logger: AppLogger,
        infra: InfrastructureContainer,
        repos: RepositoryContainer,
    ) -> None:
        self._config = config
        self._logger = logger
        self._infra = infra
        self._repos = repos

    @cached_property
    def outbox_relay(self) -> IOutboxRelayService:
        return OutboxRelayService(
            uow=self._infra.postgres_unit_of_work,
            publisher=self._infra.message_publisher,
            logger=self._logger,
            batch_size=self._config.messaging.OUTBOX_BATCH_SIZE,
        )

    @cached_property
    def health(self) -> IHealthService:
        """Dependencies checked by /readyz."""
        return HealthService(
            checks={
                "postgres": self._infra.postgres_db,
                "redis": self._infra.redis_db,
                "rabbitmq": self._infra.rabbitmq,
                "kafka": self._infra.kafka,
                "minio": self._infra.minio_client,
            },
            logger=self._logger,
        )

    # scaffold:services
