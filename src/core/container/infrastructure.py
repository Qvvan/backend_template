from __future__ import annotations

from functools import cached_property

from src.core.config import Config, MessageBroker
from src.core.logger import AppLogger
from src.infrastructure.messaging.kafka.client import KafkaClient
from src.infrastructure.messaging.kafka.publisher import KafkaMessagePublisher
from src.infrastructure.messaging.rabbitmq.client import RabbitMQClient
from src.infrastructure.messaging.rabbitmq.publisher import RabbitMQMessagePublisher
from src.infrastructure.repository.postgresql.client.connection import PostgresConnectionPool
from src.infrastructure.repository.postgresql.client.query_executor import PostgresQueryExecutor
from src.infrastructure.repository.redis.client import RedisDB
from src.infrastructure.storage.minio.client import MinIOClient
from src.infrastructure.uow.postgres_uow import PostgresUnitOfWork
from src.interfaces.clients.db.query_executor import IQueryExecutor
from src.interfaces.messaging.publisher import IMessagePublisher


class InfrastructureContainer:
    def __init__(self, config: Config, logger: AppLogger) -> None:
        self._config = config
        self._logger = logger

    @cached_property
    def postgres_db(self) -> PostgresConnectionPool:
        return PostgresConnectionPool(
            user=self._config.postgres.USER,
            password=self._config.postgres.PASSWORD.get_secret_value(),
            host=self._config.postgres.HOST,
            port=self._config.postgres.PORT,
            database=self._config.postgres.DATABASE,
            pool_size=self._config.postgres.POOL_SIZE,
            logger=self._logger,
        )

    # [if redis]
    @cached_property
    def redis_db(self) -> RedisDB:
        return RedisDB(
            logger=self._logger,
            host=self._config.redis.HOST,
            port=self._config.redis.PORT,
            db=self._config.redis.DB,
            password=self._config.redis.PASSWORD.get_secret_value() if self._config.redis.PASSWORD else None,
            decode_responses=self._config.redis.DECODE_RESPONSES,
            socket_timeout=self._config.redis.SOCKET_TIMEOUT,
            socket_connect_timeout=self._config.redis.SOCKET_CONNECT_TIMEOUT,
        )

    # [endif]

    # [if rabbitmq]
    @cached_property
    def rabbitmq(self) -> RabbitMQClient:
        return RabbitMQClient(
            user=self._config.rabbitmq.USER,
            password=self._config.rabbitmq.PASSWORD.get_secret_value(),
            host=self._config.rabbitmq.HOST,
            port=self._config.rabbitmq.PORT,
            vhost=self._config.rabbitmq.VHOST,
            tls_enabled=self._config.rabbitmq.TLS_ENABLED,
            cert_path=self._config.rabbitmq.CERT_PATH,
            prefetch_count=self._config.rabbitmq.PREFETCH_COUNT,
            retry_delays=self._config.rabbitmq.RETRY_DELAYS,
            logger=self._logger,
        )

    # [endif]

    # [if kafka]
    @cached_property
    def kafka(self) -> KafkaClient:
        return KafkaClient(
            bootstrap_servers=self._config.kafka.BOOTSTRAP_SERVERS,
            client_id=self._config.kafka.CLIENT_ID,
            security_protocol=self._config.kafka.SECURITY_PROTOCOL,
            sasl_mechanism=self._config.kafka.SASL_MECHANISM,
            sasl_username=self._config.kafka.SASL_USERNAME,
            sasl_password=(
                self._config.kafka.SASL_PASSWORD.get_secret_value() if self._config.kafka.SASL_PASSWORD else None
            ),
            auto_offset_reset=self._config.kafka.AUTO_OFFSET_RESET,
            max_retries=self._config.kafka.MAX_RETRIES,
            retry_backoff=self._config.kafka.RETRY_BACKOFF,
            logger=self._logger,
        )

    # [endif]

    # [if messaging]
    @cached_property
    def message_publisher(self) -> IMessagePublisher:
        # [if kafka and rabbitmq]
        if self._config.messaging.PUBLISHER == MessageBroker.KAFKA:
            return KafkaMessagePublisher(kafka=self.kafka)
        # [endif]
        # [if rabbitmq]
        return RabbitMQMessagePublisher(rabbit=self.rabbitmq)
        # [endif]
        # [ifc kafka and not rabbitmq]
        # return KafkaMessagePublisher(kafka=self.kafka)
        # [endif]

    # [endif]

    @cached_property
    def postgresql_query_executor(self) -> IQueryExecutor:
        return PostgresQueryExecutor(connection_pool=self.postgres_db)

    @cached_property
    def postgres_unit_of_work(self) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(pool=self.postgres_db)

    # [if minio]
    @cached_property
    def minio_client(self) -> MinIOClient:
        return MinIOClient(
            logger=self._logger,
            endpoint=f"{self._config.minio.HOST}:{self._config.minio.PORT}",
            access_key=self._config.minio.ACCESS_KEY,
            secret_key=self._config.minio.SECRET_KEY.get_secret_value(),
            secure=self._config.minio.SECURE,
        )

    # [endif]

    async def close(self) -> None:
        if "postgres_db" in self.__dict__:
            await self.postgres_db.close()
        # [if redis]
        if "redis_db" in self.__dict__:
            await self.redis_db.close()
        # [endif]
        # [if rabbitmq]
        if "rabbitmq" in self.__dict__:
            await self.rabbitmq.close()
        # [endif]
        # [if kafka]
        if "kafka" in self.__dict__:
            await self.kafka.close()
        # [endif]
        # [if minio]
        if "minio_client" in self.__dict__:
            await self.minio_client.close()
        # [endif]
