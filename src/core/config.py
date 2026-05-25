from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")


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


class RedisConfig(ConfigBase):
    """Redis cache_client settings"""
    model_config = SettingsConfigDict(env_prefix="REDIS_", frozen=True)

    HOST: str
    PORT: int
    DB: int
    PASSWORD: SecretStr | None = None
    DECODE_RESPONSES: bool = True
    SOCKET_TIMEOUT: float = 5.0
    SOCKET_CONNECT_TIMEOUT: float = 5.0


class Config(ConfigBase):
    """Главный класс конфигурации"""

    app: AppConfig = Field(default_factory=AppConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
