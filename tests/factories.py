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
    redis: RedisConfig | None = None,
    rabbitmq: RabbitMQConfig | None = None,
    kafka: KafkaConfig | None = None,
    minio: MinIOConfig | None = None,
) -> Config:
    """Config that does not depend on environment variables; nothing connects until first use."""
    return Config(
        app=AppConfig(DEBUG=True, CORS_ORIGINS=[]),
        logging=LoggingConfig(LEVEL="DEBUG"),
        postgres=postgres
        or PostgresConfig(HOST="localhost", PORT=5432, DATABASE="test", USER="test", PASSWORD=SecretStr("test")),
        redis=redis or RedisConfig(HOST="localhost", PORT=6379, DB=0),
        rabbitmq=rabbitmq
        or RabbitMQConfig(
            HOST="localhost", PORT=5672, USER="guest", PASSWORD=SecretStr("guest"), VHOST="/", TLS_ENABLED=False
        ),
        kafka=kafka or KafkaConfig(BOOTSTRAP_SERVERS="localhost:9092"),
        minio=minio
        or MinIOConfig(HOST="localhost", PORT=9000, ACCESS_KEY="minioadmin", SECRET_KEY=SecretStr("minioadmin")),
    )
