from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigBase(BaseSettings):
    # Real environment variables take precedence over values from .env.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class PostgresConfig(ConfigBase):
    """Настройки базы данных"""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", frozen=True)

    HOST: str
    PORT: int
    DATABASE: str
    USER: str
    PASSWORD: SecretStr
    POOL_SIZE: int = 5


class LoggingConfig(ConfigBase):
    """Настройки логирования"""

    model_config = SettingsConfigDict(env_prefix="LOG_", frozen=True)

    LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


class AppConfig(ConfigBase):
    """Основные настройки приложения"""

    model_config = SettingsConfigDict(env_prefix="APP_", frozen=True)

    DEBUG: bool
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["*"])


# [if rabbitmq]
class RabbitMQConfig(ConfigBase):
    """Настройки RabbitMQ"""

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", frozen=True)

    HOST: str
    PORT: int
    USER: str
    PASSWORD: SecretStr
    VHOST: str
    TLS_ENABLED: bool
    CERT_PATH: str | None = None
    PREFETCH_COUNT: int = 10
    # Delay before each retry of a failed message, seconds; after the last one it goes to <queue>.dlq
    RETRY_DELAYS: tuple[float, ...] = (1.0, 10.0, 60.0)


# [endif]


# [if kafka]
class KafkaConfig(ConfigBase):
    """Настройки Kafka"""

    model_config = SettingsConfigDict(env_prefix="KAFKA_", frozen=True)

    BOOTSTRAP_SERVERS: str = "localhost:9092"
    CLIENT_ID: str = "backend_template"
    SECURITY_PROTOCOL: Literal["PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL"] = "PLAINTEXT"
    SASL_MECHANISM: str | None = None
    SASL_USERNAME: str | None = None
    SASL_PASSWORD: SecretStr | None = None
    AUTO_OFFSET_RESET: Literal["latest", "earliest", "none"] = "latest"
    # In-process retries of a failed message (backoff doubles each time); then it goes to <topic>.dlq
    MAX_RETRIES: int = 3
    RETRY_BACKOFF: float = 1.0


# [endif]


# [if redis]
class RedisConfig(ConfigBase):
    """Настройки Redis"""

    model_config = SettingsConfigDict(env_prefix="REDIS_", frozen=True)

    HOST: str
    PORT: int
    DB: int
    PASSWORD: SecretStr | None = None
    DECODE_RESPONSES: bool = True
    SOCKET_TIMEOUT: float = 5.0
    SOCKET_CONNECT_TIMEOUT: float = 5.0


# [endif]


# [if minio]
class MinIOConfig(ConfigBase):
    """MinIO object storage settings"""

    model_config = SettingsConfigDict(env_prefix="MINIO_", frozen=True)

    HOST: str
    PORT: int
    ACCESS_KEY: str
    SECRET_KEY: SecretStr
    SECURE: bool = False


# [endif]


# [if messaging]
class MessageBroker(StrEnum):
    # [if rabbitmq]
    RABBITMQ = "rabbitmq"
    # [endif]
    # [if kafka]
    KAFKA = "kafka"
    # [endif]


class MessagingConfig(ConfigBase):
    """Publishing of integration events and the transactional outbox"""

    model_config = SettingsConfigDict(env_prefix="MESSAGING_", frozen=True)

    # [if rabbitmq]
    PUBLISHER: MessageBroker = MessageBroker.RABBITMQ
    # [endif]
    # [ifc kafka and not rabbitmq]
    # PUBLISHER: MessageBroker = MessageBroker.KAFKA
    # [endif]
    OUTBOX_BATCH_SIZE: int = 100
    OUTBOX_POLL_INTERVAL: float = 1.0


# [endif]


class TelemetryConfig(ConfigBase):
    """OpenTelemetry tracing (OTLP over HTTP). Names match the standard OTEL_* variables."""

    model_config = SettingsConfigDict(env_prefix="OTEL_", frozen=True)

    ENABLED: bool = False
    SERVICE_NAME: str = "backend_template"
    EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318"


class Config(ConfigBase):
    """Главный класс конфигурации"""

    model_config = SettingsConfigDict(frozen=True)

    app: AppConfig = Field(default_factory=AppConfig)  # type: ignore[arg-type]
    logging: LoggingConfig = Field(default_factory=LoggingConfig)  # type: ignore[arg-type]
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)  # type: ignore[arg-type]
    # [if rabbitmq]
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)  # type: ignore[arg-type]
    # [endif]
    # [if kafka]
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)  # type: ignore[arg-type]
    # [endif]
    # [if redis]
    redis: RedisConfig = Field(default_factory=RedisConfig)  # type: ignore[arg-type]
    # [endif]
    # [if minio]
    minio: MinIOConfig = Field(default_factory=MinIOConfig)  # type: ignore[arg-type]
    # [endif]
    # [if messaging]
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    # [endif]
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
