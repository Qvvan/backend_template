from __future__ import annotations

from pydantic import SecretStr

from src.core.config import (
    AppConfig,
    Config,
    KafkaConfig,
    LoggingConfig,
    MinIOConfig,
    PostgresConfig,
    RabbitMQConfig,
    RedisConfig,
)


def make_config(
    *,
    postgres: PostgresConfig | None = None,
    # [if redis]
    redis: RedisConfig | None = None,
    # [endif]
    # [if rabbitmq]
    rabbitmq: RabbitMQConfig | None = None,
    # [endif]
    # [if kafka]
    kafka: KafkaConfig | None = None,
    # [endif]
    # [if minio]
    minio: MinIOConfig | None = None,
    # [endif]
) -> Config:
    """Config that does not depend on environment variables; nothing connects until first use."""
    return Config(
        app=AppConfig(DEBUG=True, CORS_ORIGINS=[]),
        logging=LoggingConfig(LEVEL="DEBUG"),
        postgres=postgres
        or PostgresConfig(HOST="localhost", PORT=5432, DATABASE="test", USER="test", PASSWORD=SecretStr("test")),
        # [if redis]
        redis=redis or RedisConfig(HOST="localhost", PORT=6379, DB=0),
        # [endif]
        # [if rabbitmq]
        rabbitmq=rabbitmq
        or RabbitMQConfig(
            HOST="localhost", PORT=5672, USER="guest", PASSWORD=SecretStr("guest"), VHOST="/", TLS_ENABLED=False
        ),
        # [endif]
        # [if kafka]
        kafka=kafka or KafkaConfig(BOOTSTRAP_SERVERS="localhost:9092"),
        # [endif]
        # [if minio]
        minio=minio
        or MinIOConfig(HOST="localhost", PORT=9000, ACCESS_KEY="minioadmin", SECRET_KEY=SecretStr("minioadmin")),
        # [endif]
    )
