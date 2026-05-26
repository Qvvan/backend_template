# CLAUDE.md — Правила разработки backend_template

## 1. Структура проекта

```
backend_template/
├── src/
│   ├── main.py                              # Точка входа — только app factory
│   ├── api/                                 # Presentation layer
│   │   ├── __init__.py                      # Агрегация роутеров
│   │   ├── dependencies.py                  # FastAPI DI-функции
│   │   ├── exception_handlers.py            # Единственное место для перехвата ошибок
│   │   ├── health.py                        # Health-check endpoints
│   │   ├── middleware/
│   │   │   └── request_logging.py           # Request ID, логирование входящих запросов
│   │   └── v1/
│   │       ├── __init__.py                  # v1_router
│   │       └── schemas/                     # Pydantic схемы запросов и ответов
│   ├── core/                                # Composition root support
│   │   ├── config.py                        # Pydantic BaseSettings (только здесь)
│   │   ├── exceptions.py                    # Иерархия доменных исключений
│   │   ├── logger.py                        # AppLogger (JSON, ContextVar request_id)
│   │   └── container/
│   │       ├── __init__.py                  # Container — главный DI-контейнер
│   │       ├── infrastructure.py            # InfrastructureContainer
│   │       ├── repositories.py              # RepositoryContainer
│   │       ├── services.py                  # ServiceContainer
│   │       └── workers.py                   # WorkerContainer + AsyncScheduler
│   ├── domain/
│   │   └── entities/                        # Все dataclass-модели и бизнес-логика
│   ├── infrastructure/                      # Infrastructure layer
│   │   ├── http/                            # HTTP-клиенты (отдельные классы)
│   │   ├── messaging/
│   │   │   ├── consumer.py                  # BackendConsumer — маршрутизирует очереди
│   │   │   ├── publisher.py                 # MessagePublisher
│   │   │   ├── rabbitmq.py                  # RabbitMQClient — транспорт
│   │   │   └── handlers/                    # Хендлеры сообщений из очередей
│   │   │       ├── schemas/                 # Pydantic контракты входящих сообщений
│   │   │       └── <name>_handler.py        # Один хендлер = одна очередь
│   │   ├── repository/
│   │   │   ├── postgresql/
│   │   │   │   └── client/
│   │   │   │       ├── connection.py        # PostgresConnectionPool
│   │   │   │       ├── query_executor.py    # PostgresQueryExecutor
│   │   │   │       └── transaction_executor.py  # PostgresTransactionExecutor
│   │   │   └── redis/
│   │   │       ├── client.py                # RedisDB
│   │   │       └── repository.py            # RedisRepository
│   │   └── uow/
│   │       ├── postgres_uow.py              # PostgresUnitOfWork
│   │       └── transaction_session.py       # TransactionSession (реестр репозиториев)
│   ├── interfaces/                          # Абстракции — только ABC / Protocol
│   │   ├── clients/
│   │   │   ├── cache_client/
│   │   │   │   ├── client.py               # ICacheDB
│   │   │   │   └── repository.py           # ICacheRepository
│   │   │   └── db/
│   │   │       ├── connection.py            # IDBBase, IDBConnectable, IDBTransactional
│   │   │       ├── query_executor.py        # IFetch, IFetchRow, IExecutor, IQueryExecutor
│   │   │       └── uow.py                   # IUnitOfWork
│   │   ├── messaging/
│   │   │   ├── client.py                    # IAMQPClient, IQueue, AMQPExchangeType
│   │   │   ├── consumer.py                  # IConsumer
│   │   │   └── publisher.py                 # IMessagePublisher
│   │   ├── repositories/                    # Интерфейсы репозиториев (по одному на агрегат)
│   │   ├── services/                        # Интерфейсы сервисов
│   │   └── workers/
│   │       └── worker.py                    # IWorker
│   ├── services/                            # Application layer — оркестрация
│   ├── utils/                               # Вспомогательные утилиты без бизнес-логики
│   └── workers/
│       └── scheduler.py                     # AsyncScheduler
├── migrations/                              # yoyo SQL-миграции
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml                           # Зависимости, ruff, pytest
└── yoyo.ini
```

---

## 2. Слои архитектуры

Зависимости строго сверху вниз. Нижний слой **никогда** не знает о верхнем.

```
Presentation     →  src/api/,  src/infrastructure/messaging/handlers/
Application      →  src/services/
Domain           →  src/domain/entities/
Infrastructure   →  src/infrastructure/
Composition Root →  src/core/container/,  src/main.py
```

---

### 2.1 ENDPOINTS (`src/api/v1/`)

**Правила:**

- Принимает запрос **только через Pydantic схему** из `src/api/v1/schemas/`.
- Маппит схему в доменную модель (`@dataclass` из `src/domain/entities/`).
- Вызывает **ровно один** сервис.
- Маппит результат обратно в response-схему.
- **Не содержит бизнес-логику.** Не знает порядка операций.
- **Не использует `try/except`.** Ошибки ловит только `exception_handler`.
- **Никогда не вызывает два сервиса подряд.**
- Получает зависимости через `Depends()` из `src/api/dependencies.py`.

**Пример из проекта — как должно быть:**

```python
# src/api/v1/schemas/user_schemas.py
from __future__ import annotations
from pydantic import BaseModel

class CreateUserRequest(BaseModel):
    name: str
    email: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
```

```python
# src/api/v1/users.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from src.api.dependencies import get_user_service
from src.api.v1.schemas.user_schemas import CreateUserRequest, UserResponse
from src.domain.entities.user import UserEntity
from src.interfaces.services.user_service import IUserService

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    service: IUserService = Depends(get_user_service),
) -> UserResponse:
    entity = UserEntity(name=body.name, email=body.email)
    result = await service.create(entity)
    return UserResponse(id=result.id, name=result.name, email=result.email)
```

**Что сейчас в проекте:**
`src/api/v1/schemas/` — пустая папка. При добавлении эндпоинта схемы обязательно создаются здесь.

**ЗАПРЕЩЕНО в эндпоинте:**
```python
# НЕПРАВИЛЬНО — бизнес-логика в эндпоинте
@router.post("/users/")
async def create_user(body: CreateUserRequest, db = Depends(get_postgres_db)):
    user = await db.fetchrow("SELECT * FROM users WHERE email = $1", body.email)
    if user:
        raise HTTPException(400, "already exists")   # ← бизнес-логика здесь
    ...

# НЕПРАВИЛЬНО — два сервиса
@router.post("/orders/")
async def create_order(body: ..., order_svc = ..., notify_svc = ...):
    result = await order_svc.create(...)
    await notify_svc.send(...)          # ← второй сервис запрещён
```

---

### 2.2 CONSUMERS / HANDLERS (`src/infrastructure/messaging/handlers/`)

**Правила:**

- `consumer.py` (BackendConsumer) — только регистрирует очереди и маршрутизирует к хендлерам. Никакой логики.
- Для каждой очереди — **обязательная Pydantic схема** в `handlers/schemas/`.
- Хендлер парсит сообщение через схему, маппит в `@dataclass`, вызывает **ровно один** сервис.
- Логирует только: начало обработки, завершение.
- **Никакого `try/except`**, никакой бизнес-логики.

**Структура:**

```
infrastructure/messaging/handlers/
├── schemas/
│   └── user_schemas.py          # Pydantic контракты входящих сообщений
└── user_handler.py              # Хендлеры для очередей пользователей
```

**Пример:**

```python
# src/infrastructure/messaging/handlers/schemas/user_schemas.py
from __future__ import annotations
from pydantic import BaseModel

class UserCreatedMessage(BaseModel):
    user_id: str
    email: str
    name: str
```

```python
# src/infrastructure/messaging/handlers/user_handler.py
from __future__ import annotations
from src.core.logger import AppLogger
from src.domain.entities.user import UserEntity
from src.infrastructure.messaging.handlers.schemas.user_schemas import UserCreatedMessage
from src.interfaces.services.user_service import IUserService

class UserMessageHandler:
    __slots__ = ("_service", "_logger")

    def __init__(self, service: IUserService, logger: AppLogger) -> None:
        self._service = service
        self._logger = logger

    async def handle_user_created(self, msg: UserCreatedMessage) -> None:
        entity = UserEntity(id=msg.user_id, name=msg.name, email=msg.email)
        self._logger.info("Handling user_created", user_id=msg.user_id)
        await self._service.on_user_created(entity)
        self._logger.info("user_created handled", user_id=msg.user_id)
```

```python
# src/infrastructure/messaging/consumer.py (реальный файл проекта)
async def register_consumers(self) -> None:
    handler = UserMessageHandler(service=..., logger=self._logger)
    await self._rabbit.consume(
        queue_name="user.created",
        handler=handler.handle_user_created,
        model=UserCreatedMessage,
        exchange="users",
        routing_key="user.created",
    )
    self._logger.info("Consumer started")
```

**ЗАПРЕЩЕНО в хендлере:**
```python
# НЕПРАВИЛЬНО — бизнес-логика в хендлере
async def handle_user_created(self, msg: UserCreatedMessage) -> None:
    if msg.email.endswith("@spam.com"):      # ← бизнес-логика
        return
    await self._repo.save(...)               # ← прямой вызов репозитория

# НЕПРАВИЛЬНО — неверная сигнатура (RabbitMQClient передаёт уже валидированный объект, не dict)
async def handle_user_created(self, data: dict[str, object]) -> None:
    msg = UserCreatedMessage.model_validate(data)   # ← двойная валидация, хендлер принимает не dict
```

---

### 2.3 SERVICES (`src/services/`)

**Правила:**

- Знают **последовательность операций**.
- `IUnitOfWork.begin()` — только когда одна операция меняет **несколько таблиц сразу** (нужна атомарность). Одна таблица или только чтение — `IUnitOfWork` не нужен.
- Запись в одну таблицу → репозиторий напрямую.
- Чтение из нескольких таблиц → репозитории напрямую, без UoW.
- Запись/удаление/обновление в нескольких таблицах → `IUnitOfWork.begin()`.
- Поднимают **доменные исключения** из `src/core/exceptions.py`.
- Делегируют бизнес-логику в методы `entity`. Сами логику **не содержат**.
- **Никогда не получают `Config`.**
- Зависят только от интерфейсов (`interfaces/`), не от конкретных классов.

**Пример:**

```python
# src/interfaces/services/user_service.py
from __future__ import annotations
from abc import ABC, abstractmethod
from src.domain.entities.user import UserEntity

class IUserService(ABC):
    @abstractmethod
    async def create(self, entity: UserEntity) -> UserEntity: ...

    @abstractmethod
    async def get_by_id(self, user_id: str) -> UserEntity: ...
```

```python
# src/services/user_service.py
from __future__ import annotations
from src.core.exceptions import ConflictError, NotFoundError
from src.domain.entities.user import UserEntity
from src.interfaces.repositories.user_repository import IUserRepository
from src.interfaces.services.user_service import IUserService

class UserService(IUserService):
    __slots__ = ("_repo",)

    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

    async def create(self, entity: UserEntity) -> UserEntity:
        existing = await self._repo.find_by_email(entity.email)
        if existing:
            raise ConflictError("User with this email already exists")
        return await self._repo.save(entity)

    async def get_by_id(self, user_id: str) -> UserEntity:
        user = await self._repo.find_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user
```

**ЗАПРЕЩЕНО в сервисе:**
```python
# НЕПРАВИЛЬНО — конфиг в сервисе
class UserService:
    def __init__(self, config: Config, ...):    # ← конфиг запрещён
        self._debug = config.app.DEBUG

# НЕПРАВИЛЬНО — бизнес-логика в сервисе вместо entity
async def create(self, entity: UserEntity) -> UserEntity:
    if "@" not in entity.email:               # ← должно быть в entity.validate()
        raise ValidationError("bad email")
```

---

### 2.4 DOMAIN ENTITIES (`src/domain/entities/`)

**Правила:**

- **Только чистая бизнес-логика.** Никакого I/O, никаких внешних зависимостей.
- **Все модели данных (`@dataclass`) определяются только здесь.** Нигде больше.
- Никаких исключений и никакой обработки ошибок.
- Никаких импортов из `infrastructure`, `services`, `api`.

**Пример:**

```python
# src/domain/entities/user.py
from __future__ import annotations
from dataclasses import dataclass, field
import uuid

@dataclass
class UserEntity:
    name: str
    email: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def full_display(self) -> str:
        return f"{self.name} <{self.email}>"

    def is_valid_email(self) -> bool:
        return "@" in self.email and "." in self.email.split("@")[-1]
```

**Что сейчас в проекте:** `src/domain/entities/` — пустая папка. Все новые `@dataclass` создаются здесь.

**ЗАПРЕЩЕНО:**
```python
# НЕПРАВИЛЬНО — dataclass в репозитории
# src/infrastructure/repository/postgresql/user_repo.py
@dataclass
class UserRow:                          # ← модель не в domain/entities
    id: str
    email: str

# НЕПРАВИЛЬНО — I/O в entity
@dataclass
class UserEntity:
    async def save(self) -> None:       # ← I/O в domain запрещён
        await db.execute(...)
```

---

### 2.5 REPOSITORIES (`src/infrastructure/repository/`)

**Правила:**

- Знают только **SQL-запросы**.
- Принимают `IQueryExecutor` или `PostgresTransactionExecutor`.
- **Никакой бизнес-логики, никакой обработки ошибок.**
- Строят запрос → передают в `query_executor` → маппят результат в `@dataclass` из `domain/entities/` → возвращают.
- Интерфейс репозитория — в `src/interfaces/repositories/`.

**Пример из проекта (`RedisRepository` — реальный класс):**

```python
# src/infrastructure/repository/redis/repository.py (реальный файл)
class RedisRepository(ICacheRepository):
    __slots__ = ("_client",)

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, expire: int | None = None) -> bool:
        if expire is not None:
            return await self._client.setex(key, expire, value)
        return await self._client.set(key, value)
```

**Пример PostgreSQL-репозитория:**

```python
# src/interfaces/repositories/user_repository.py
from __future__ import annotations
from abc import ABC, abstractmethod
from src.domain.entities.user import UserEntity

class IUserRepository(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: str) -> UserEntity | None: ...

    @abstractmethod
    async def save(self, entity: UserEntity) -> UserEntity: ...
```

```python
# src/infrastructure/repository/postgresql/user_repository.py
from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from src.domain.entities.user import UserEntity
from src.interfaces.clients.db.query_executor import IQueryExecutor
from src.interfaces.repositories.user_repository import IUserRepository

class PostgresUserRepository(IUserRepository):
    __slots__ = ("_executor",)

    def __init__(self, executor: IQueryExecutor) -> None:
        self._executor = executor

    async def find_by_id(self, user_id: str) -> UserEntity | None:
        row = await self._executor.fetchrow(
            "SELECT id, name, email FROM users WHERE id = $1", user_id
        )
        return self._map(row) if row else None

    async def save(self, entity: UserEntity) -> UserEntity:
        row = await self._executor.fetchrow(
            "INSERT INTO users (id, name, email) VALUES ($1, $2, $3) RETURNING *",
            entity.id, entity.name, entity.email,
        )
        return self._map(row)  # type: ignore[arg-type]

    @staticmethod
    def _map(row: Mapping[str, Any]) -> UserEntity:
        return UserEntity(id=row["id"], name=row["name"], email=row["email"])
```

**ЗАПРЕЩЕНО в репозитории:**
```python
# НЕПРАВИЛЬНО — бизнес-логика в репозитории
async def find_active_users(self) -> list[UserEntity]:
    rows = await self._executor.fetch("SELECT * FROM users")
    return [u for u in rows if u["is_active"]]   # ← фильтрация = бизнес-логика

# НЕПРАВИЛЬНО — обработка ошибок в репозитории
async def save(self, entity: UserEntity) -> UserEntity:
    try:
        ...
    except asyncpg.UniqueViolationError:
        raise ConflictError(...)              # ← это задача сервиса
```

---

### 2.6 WORKERS (`src/workers/`, `src/interfaces/workers/`)

**Правила:**

- Реализуют `IWorker` из `src/interfaces/workers/worker.py`.
- `start(stop: asyncio.Event)` — единственная точка входа.
- Вызывают **один сервис** по расписанию или триггеру.
- Логируют только: начал работу, завершил работу, причину остановки.
- **Никакой бизнес-логики, никакого прямого обращения к БД или кэшу.**
- Регистрируются в `WorkerContainer` и передаются в `AsyncScheduler`.

**Из проекта — `AsyncScheduler` (`src/workers/scheduler.py`) уже реализован:**
- `start()` — запускает все воркеры как asyncio Tasks
- `stop_worker(name)` — посылает сигнал остановки конкретному воркеру
- `shutdown()` — graceful shutdown всех воркеров с таймаутом 30 сек

**Пример воркера:**

```python
# src/workers/cleanup_worker.py
from __future__ import annotations
import asyncio
from src.core.logger import AppLogger
from src.interfaces.services.cleanup_service import ICleanupService
from src.interfaces.workers.worker import IWorker

class CleanupWorker(IWorker):
    __slots__ = ("_service", "_logger", "_interval")

    def __init__(self, service: ICleanupService, logger: AppLogger, interval: int) -> None:
        self._service = service
        self._logger = logger
        self._interval = interval

    @property
    def name(self) -> str:
        return "cleanup_worker"

    async def start(self, stop: asyncio.Event) -> None:
        self._logger.info("CleanupWorker started")
        while not stop.is_set():
            await self._service.run_cleanup()
            await asyncio.wait_for(asyncio.shield(stop.wait()), self._interval)
        self._logger.info("CleanupWorker stopped")
```

**ЗАПРЕЩЕНО в воркере:**
```python
# НЕПРАВИЛЬНО — прямое обращение к БД
async def start(self, stop: asyncio.Event) -> None:
    async with pool.get_connection() as conn:       # ← запрещено
        await conn.execute("DELETE FROM sessions")

# НЕПРАВИЛЬНО — конфиг в воркере
def __init__(self, config: Config, ...):            # ← запрещено
```

---

### 2.7 COMPOSITION ROOT (`src/core/container/`, `src/main.py`)

**Правила:**

- **Единственное место, где используется `Config`.**
- Конфиг **не передаётся** дальше ни в один слой.
- Здесь собираются все зависимости через `cached_property`.
- `close()` закрывает соединения только если они были открыты (проверка через `__dict__`).

**Правила конфигурации (`src/core/config.py`):**

- Все секции Config (`PostgresConfig`, `RedisConfig`, `RabbitMQConfig`, `AppConfig`) используют `frozen=True` — конфиг неизменяем после инициализации, это защита от случайной мутации в рантайме.
- Пароли и любые секреты — только `SecretStr`. Получить значение — `.get_secret_value()`. Нельзя передавать `SecretStr` напрямую в строку или SQL.
- `Config` читается из переменных окружения через `SettingsConfigDict(env_prefix="...", frozen=True)`. Никакого `os.getenv()` нигде кроме `config.py`.

```python
# ПРАВИЛЬНО — SecretStr для секретов, frozen=True для каждой секции
class PostgresConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", frozen=True)
    PASSWORD: SecretStr

# В контейнере — единственное место, где достают значение:
PostgresConnectionPool(password=self._config.postgres.PASSWORD.get_secret_value(), ...)

# НЕПРАВИЛЬНО — plain str для секрета
class PostgresConfig(ConfigBase):
    PASSWORD: str           # ← утечёт в логи, repr, трейсбеки

# НЕПРАВИЛЬНО — os.getenv вне config.py
import os
db_password = os.getenv("POSTGRES_PASSWORD")    # ← запрещено
```

**Реальная структура из проекта:**

```python
# src/core/container/__init__.py (реальный файл)
class Container:
    __slots__ = ("config", "infra", "logger", "repos", "services", "workers")

    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = AppLogger(level=config.logging.LEVEL)
        self.infra = InfrastructureContainer(config, self.logger)
        self.repos = RepositoryContainer(self.infra)
        self.services = ServiceContainer(config=config, infra=self.infra, repos=self.repos)
        self.workers = WorkerContainer(logger=self.logger, services=self.services)

    async def closer(self) -> None:
        await self.workers.close()
        await self.infra.close()
```

```python
# src/core/container/infrastructure.py (реальный файл)
class InfrastructureContainer:
    @cached_property
    def postgres_db(self) -> PostgresConnectionPool:
        return PostgresConnectionPool(
            user=self._config.postgres.USER,
            password=self._config.postgres.PASSWORD.get_secret_value(),
            ...
        )

    async def close(self) -> None:
        if "postgres_db" in self.__dict__:    # не создаём соединение ради закрытия
            await self.postgres_db.close()
```

**Dependencies (`src/api/dependencies.py` — реальный файл):**

```python
def get_postgres_db(request: Request) -> IDBTransactional:
    return request.app.state.container.infra.postgres_db

def get_rabbitmq(request: Request) -> IAMQPClient:
    return request.app.state.container.infra.rabbitmq
```

**ЗАПРЕЩЕНО:**
```python
# НЕПРАВИЛЬНО — конфиг в сервисе
class UserService:
    def __init__(self, config: AppConfig): ...      # ← конфиг запрещён вне контейнера

# НЕПРАВИЛЬНО — конфиг в эндпоинте
@router.get("/")
async def get(config: Config = Depends(...)): ...   # ← запрещено
```

---

### 2.8 EXCEPTION HANDLER (`src/api/exception_handlers.py`)

**Правила:**

- **Единственное место**, где исключения перехватываются на уровне presentation.
- Каждое доменное исключение из `src/core/exceptions.py` обязано быть зарегистрировано явно.
- Возвращает `ORJSONResponse` с единообразной структурой.

**Реальный файл проекта:**

```python
# src/api/exception_handlers.py
def register_errors(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(req: Request, exc: AppError) -> ORJSONResponse:
        return ORJSONResponse(
            status_code=exc.http_status_code,
            content={"status": "error", "code": exc.code, "comment": exc.message, "obj": None},
        )
```

**Иерархия исключений (`src/core/exceptions.py` — реальный файл):**

```python
AppError             → HTTP 500 (базовое)
├── DatabaseError    → HTTP 500
├── ValidationError  → HTTP 422
├── NotFoundError    → HTTP 404
└── ConflictError    → HTTP 409
```

**Правило:** если добавляется новое исключение — оно **обязано** быть зарегистрировано в `register_errors()`.

---

### 2.9 INTERFACES (`src/interfaces/`)

**Правила:**

- Только `ABC` или `Protocol`. **Никаких конкретных классов.**
- **Никаких импортов из `infrastructure`.** Нарушение = дизайн-дефект.
- Каждый интерфейс репозитория — в `src/interfaces/repositories/`.
- Каждый интерфейс сервиса — в `src/interfaces/services/`.

**Реальные интерфейсы проекта:**

| Интерфейс | Файл | Реализация |
|---|---|---|
| `IAMQPClient` | `interfaces/messaging/client.py` | `RabbitMQClient` |
| `IMessagePublisher` | `interfaces/messaging/publisher.py` | `MessagePublisher` |
| `IConsumer` | `interfaces/messaging/consumer.py` | `BackendConsumer` |
| `ICacheDB` | `interfaces/clients/cache_client/client.py` | `RedisDB` |
| `ICacheRepository` | `interfaces/clients/cache_client/repository.py` | `RedisRepository` |
| `IDBTransactional` | `interfaces/clients/db/connection.py` | `PostgresConnectionPool` |
| `IQueryExecutor` | `interfaces/clients/db/query_executor.py` | `PostgresQueryExecutor`, `PostgresTransactionExecutor` |
| `IUnitOfWork` | `interfaces/clients/db/uow.py` | `PostgresUnitOfWork` |
| `IWorker` | `interfaces/workers/worker.py` | кастомные воркеры |

**Контракт `health_check()` для инфраструктурных клиентов:**

Каждый инфраструктурный клиент (`PostgresConnectionPool`, `RedisDB`, `RabbitMQClient`) обязан реализовывать `health_check() -> bool`. Метод возвращает `True` если соединение живо, `False` при любой ошибке — без исключений наружу. Используется в `src/api/health.py`.

```python
# ПРАВИЛЬНО — health_check в каждом инфра-клиенте
async def health_check(self) -> bool:
    try:
        async with asyncio.timeout(5):
            async with self.get_connection() as conn:
                await conn.execute("SELECT 1")
        return True
    except Exception as e:
        self._logger.error("Health check failed", error=e)
        return False
```

**ЗАПРЕЩЕНО в интерфейсах:**
```python
# НЕПРАВИЛЬНО — инфраструктурный тип в интерфейсе
import asyncpg

class IUserRepository(ABC):
    async def find(self) -> asyncpg.Record: ...     # ← asyncpg = инфраструктура
```

---

## 3. Запрещено — полный список

| # | Нарушение | Где нельзя |
|---|---|---|
| 1 | `Config` передаётся за пределы `container/` и `main.py` | Везде кроме Container |
| 2 | Бизнес-логика (условия, вычисления, правила) | Endpoints, Consumers/Handlers, Workers, Repositories |
| 3 | Два и более вызовов сервисов в одном эндпоинте или хендлере | Endpoints, Handlers |
| 4 | `try/except` в эндпоинтах и хендлерах сообщений | Endpoints, Handlers |
| 5 | `@dataclass` вне `src/domain/entities/` | Везде кроме domain |
| 6 | Голые типы: `list`, `dict`, `Any` без параметров | Везде |
| 7 | Магические строки и числа без `Enum` | Везде |
| 8 | Зависимость от конкретного класса вместо интерфейса (`ABC`/`Protocol`) | Services, Handlers, Workers |
| 9 | Blocking I/O (синхронные вызовы БД, файлов, HTTP) | Везде |
| 10 | Импорт `infrastructure`-типов (asyncpg, aioredis) в `interfaces/` | Interfaces |
| 11 | Прямое обращение к БД или кэшу в воркере | Workers |
| 12 | Логика маршрутизации сообщений вне `consumer.py` | — |
| 13 | Отсутствие Pydantic-схемы для очереди | Handlers |
| 14 | Несколько агрегатов в одном репозитории | Repositories |
| 15 | `from __future__ import annotations` отсутствует в файле | Все `.py` файлы |
| 16 | Отсутствие возвращаемого типа на методе | Все классы |
| 17 | `print()` вместо `logger.*()` | Везде |
| 18 | f-строки в аргументе `message` логгера | Везде |

---

## 4. Соглашения по именованию

На основе существующего кода проекта:

| Сущность | Стиль | Пример из проекта |
|---|---|---|
| Файлы | `snake_case` | `request_logging.py`, `query_executor.py` |
| Классы | `PascalCase` | `PostgresConnectionPool`, `RabbitMQClient` |
| Интерфейсы | `I` + `PascalCase` | `IAMQPClient`, `IQueryExecutor`, `ICacheDB` |
| Методы | `snake_case` | `get_connection()`, `health_check()` |
| Константы в Enum | `UPPER_CASE` или `PascalCase` (StrEnum) | `AMQPExchangeType.Topic` |
| Приватные методы | `_snake_case` | `_ensure_connected()`, `_build_ssl_context()` |
| Контейнеры | `<Name>Container` | `InfrastructureContainer`, `WorkerContainer` |
| Сервисы | `<Name>Service` | `UserService` |
| Репозитории | `<Driver><Name>Repository` | `PostgresUserRepository`, `RedisRepository` |
| Хендлеры | `<Name>Handler` | `UserMessageHandler` |
| Воркеры | `<Name>Worker` | `CleanupWorker` |
| Схемы запроса | `<Action><Entity>Request` | `CreateUserRequest` |
| Схемы ответа | `<Entity>Response` | `UserResponse` |
| Схемы сообщений | `<Event>Message` | `UserCreatedMessage` |
| Entity | `<Name>Entity` | `UserEntity` |
| Роутеры | `<name>_router` | `v1_router`, `health_router` |

---

## 5. Правильный и неправильный код

### 5.1 Типизация

```python
# ПРАВИЛЬНО
from __future__ import annotations
from collections.abc import Mapping
from typing import Any

async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None: ...
async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]: ...

# НЕПРАВИЛЬНО
async def fetchrow(self, query, *args):       # нет типов
async def fetch(self, query) -> list:         # голый list
async def process(self, data: Any) -> dict:  # голые Any и dict
```

### 5.2 __slots__

**Правило: все классы обязаны иметь `__slots__`, кроме классов с `cached_property`.**

`cached_property` несовместим с `__slots__` (дескриптор требует `__dict__`), поэтому контейнеры (`InfrastructureContainer`, `RepositoryContainer`, `ServiceContainer`, `WorkerContainer`) — единственное исключение. Все остальные классы: сервисы, репозитории, хендлеры, воркеры, клиенты — обязаны объявлять `__slots__`.

```python
# ПРАВИЛЬНО — __slots__ на всех обычных классах
class PostgresQueryExecutor(IQueryExecutor):
    __slots__ = ("_connection_pool",)         # реальный пример из проекта

    def __init__(self, connection_pool: PostgresConnectionPool) -> None:
        self._connection_pool = connection_pool

class UserService(IUserService):
    __slots__ = ("_repo",)

    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

# ПРАВИЛЬНО — контейнер без __slots__ (cached_property требует __dict__)
class InfrastructureContainer:
    @cached_property
    def postgres_db(self) -> PostgresConnectionPool: ...

# НЕПРАВИЛЬНО — __slots__ на классе с cached_property
class InfrastructureContainer:
    __slots__ = ("_config",)                  # сломает cached_property
    @cached_property
    def postgres_db(self) -> PostgresConnectionPool: ...

# НЕПРАВИЛЬНО — нет __slots__ на обычном классе
class UserMessageHandler:
    def __init__(self, service: IUserService) -> None:   # ← забыли __slots__
        self._service = service
```

### 5.3 Зависимости через интерфейс

```python
# ПРАВИЛЬНО — зависимость от IAMQPClient (интерфейс)
# Реальный пример из src/infrastructure/messaging/consumer.py
class BackendConsumer(IConsumer):
    def __init__(self, *, rabbit: IAMQPClient, logger: AppLogger, stop: asyncio.Event) -> None:
        self._rabbit = rabbit

# ПРАВИЛЬНО — зависимость от IMessagePublisher (интерфейс)
# Реальный пример из src/infrastructure/messaging/publisher.py
class MessagePublisher(IMessagePublisher):
    def __init__(self, rabbit: IAMQPClient, logger: AppLogger) -> None:
        self._rabbit = rabbit

# НЕПРАВИЛЬНО — зависимость от конкретного класса
class UserHandler:
    def __init__(self, rabbit: RabbitMQClient): ...  # ← конкретный класс
```

### 5.4 UnitOfWork в сервисе

Правило: UoW нужен **только** когда одна операция мутирует несколько таблиц одновременно.

```python
# ПРАВИЛЬНО — одна таблица, UoW не нужен
class UserService(IUserService):
    async def create(self, entity: UserEntity) -> UserEntity:
        return await self._repo.save(entity)   # один репозиторий — напрямую

# ПРАВИЛЬНО — две таблицы меняются атомарно → UoW обязателен
# TransactionSession хранит IQueryExecutor в _tx; при добавлении UoW-фичи
# в TransactionSession добавляются @property-методы, возвращающие репозитории.
#
# src/infrastructure/uow/transaction_session.py (реальный файл):
# class TransactionSession:
#     __slots__ = ("_tx",)
#     def __init__(self, tx: IQueryExecutor) -> None: self._tx = tx
#     @property
#     def orders(self) -> PostgresOrderRepository: return PostgresOrderRepository(self._tx)
#     @property
#     def inventory(self) -> PostgresInventoryRepository: return PostgresInventoryRepository(self._tx)

class OrderService(IOrderService):
    async def place(self, order: OrderEntity) -> OrderEntity:
        async with self._uow.begin() as session:
            result = await session.orders.save(order)
            await session.inventory.decrement(order.item_id, order.qty)
            return result

# НЕПРАВИЛЬНО — UoW для записи в одну таблицу (избыточно)
async def create(self, entity: UserEntity) -> UserEntity:
    async with self._uow.begin() as session:
        return await session.users.save(entity)   # ← одна таблица, UoW не нужен

# НЕПРАВИЛЬНО — без транзакции когда меняются две таблицы
async def place(self, order: OrderEntity) -> OrderEntity:
    result = await self._order_repo.save(order)
    await self._inventory_repo.decrement(order.item_id, order.qty)  # ← потеряется при сбое
    return result
```

### 5.5 Enum вместо магических строк

```python
# ПРАВИЛЬНО — реальный пример из src/interfaces/messaging/client.py
from enum import StrEnum

class AMQPExchangeType(StrEnum):
    Direct = "direct"
    Fanout = "fanout"
    Topic = "topic"
    Headers = "headers"

# Использование:
await client.consume(exchange_type=AMQPExchangeType.Topic)

# НЕПРАВИЛЬНО
await client.consume(exchange_type="topic")    # магическая строка
```

### 5.6 Логирование

**Правила:**

- **Никогда не используем `print()`** — только методы `AppLogger`: `debug`, `info`, `warning`, `error`, `critical`.
- **Никогда не используем f-строки в `message`** — строка сообщения всегда статическая; переменные передаются как именованные поля (`**fields`), которые попадают в JSON-лог отдельными ключами.
- `logger.error()` вызывается **внутри блока `except`** — тогда `exc_info` подхватывается автоматически; снаружи `except` — используй `logger.warning()` или `logger.info()`.
- Логируем только значимые события: начало/конец обработки, аномальное поведение. Не логируем каждый SQL-запрос или внутренний шаг.

```python
# ПРАВИЛЬНО — статическое сообщение, данные как fields
self._logger.info("User created", user_id=entity.id, email=entity.email)
self._logger.warning("Retry attempt", queue="user.created", attempt=3)

# ПРАВИЛЬНО — error внутри except: exc_info добавляется автоматически
try:
    await self._repo.save(entity)
except Exception:
    self._logger.error("Failed to save user", user_id=entity.id)
    raise

# НЕПРАВИЛЬНО — f-строка в сообщении
self._logger.info(f"User {entity.id} created")          # ← нельзя

# НЕПРАВИЛЬНО — print вместо logger
print(f"User {entity.id} created")                      # ← нельзя

# НЕПРАВИЛЬНО — позиционное форматирование вместо fields
self._logger.info("User %s created", entity.id)         # ← нельзя
```

---

### 5.7 Double-check lock для lazy connect в инфра-клиентах

Все инфраструктурные клиенты с ленивым подключением используют `asyncio.Lock` с двойной проверкой — это предотвращает race condition при одновременных вызовах из разных корутин.

```python
# ПРАВИЛЬНО — паттерн из RabbitMQClient и PostgresConnectionPool
async def _ensure_connected(self) -> None:
    if not self._channel:                       # быстрая проверка без лока
        async with self._connect_lock:
            if not self._channel:               # повторная проверка под локом
                await self.connect()

# НЕПРАВИЛЬНО — нет двойной проверки (каждый вызов берёт лок)
async def _ensure_connected(self) -> None:
    async with self._connect_lock:
        if not self._channel:
            await self.connect()

# НЕПРАВИЛЬНО — нет лока (race condition при параллельных запросах)
async def _ensure_connected(self) -> None:
    if not self._channel:
        await self.connect()
```

Обязательно: `_connect_lock = asyncio.Lock()` инициализируется в `__init__`, добавляется в `__slots__`.

---

### 5.8 asyncio.timeout() vs asyncio.wait_for()

Python 3.12+. Выбор зависит от того, нужно ли пробросить `TimeoutError` выше.

```python
# asyncio.timeout() — простой кейс, ошибка остаётся внутри блока
# Используется в health_check: один вызов, ошибка поглощается
async def health_check(self) -> bool:
    try:
        async with asyncio.timeout(5):
            await self._conn.execute("SELECT 1")
        return True
    except Exception:
        return False

# asyncio.wait_for() — когда TimeoutError нужно поймать снаружи или передать
# Используется в AsyncScheduler.shutdown() с таймаутом на всю группу задач
try:
    await asyncio.wait_for(
        asyncio.gather(*self._tasks.values(), return_exceptions=True),
        timeout=30.0,
    )
except TimeoutError:
    # отменяем задачи принудительно
    for task in self._tasks.values():
        task.cancel()
```

---

### 5.9 Graceful shutdown через AsyncScheduler

```python
# Реальный пример из src/core/container/workers.py
class WorkerContainer:
    @cached_property
    def scheduler(self) -> AsyncScheduler:
        return AsyncScheduler(logger=self._logger, workers=[])

    def start(self) -> None:
        self.scheduler.start()

    async def close(self) -> None:
        await self.scheduler.shutdown()   # ждёт завершения всех воркеров (таймаут 30 сек)
```

---

## 6. Что сейчас пусто и как заполнять

| Папка | Что создать |
|---|---|
| `src/domain/entities/` | `<name>.py` с `@dataclass` для каждого агрегата |
| `src/services/` | `<name>_service.py` с классом сервиса |
| `src/interfaces/repositories/` | `<name>_repository.py` с `ABC`-интерфейсом репозитория |
| `src/interfaces/services/` | `<name>_service.py` с `ABC`-интерфейсом сервиса |
| `src/api/v1/schemas/` | `<name>_schemas.py` с Pydantic схемами запросов/ответов |
| `src/infrastructure/messaging/handlers/` | `<name>_handler.py` с классом хендлера |
| `src/infrastructure/messaging/handlers/schemas/` | `<name>_schemas.py` с Pydantic схемами сообщений |
| `src/infrastructure/http/` | `<name>_client.py` реализующий HTTP-клиент через интерфейс |

**Порядок добавления новой фичи:**
1. `domain/entities/` — создать `@dataclass`
2. `interfaces/repositories/` — создать ABC-интерфейс репозитория
3. `interfaces/services/` — создать ABC-интерфейс сервиса
4. `infrastructure/repository/postgresql/` — реализовать репозиторий
5. `services/` — реализовать сервис
6. `api/v1/schemas/` — создать Pydantic схемы
7. `api/v1/` — создать эндпоинт
8. `core/container/` — зарегистрировать в нужном контейнере
9. `api/dependencies.py` — добавить DI-функцию

---

## 7. Тестирование

### 7.1 Конфигурация

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"          # все async def тесты запускаются без декоратора
testpaths = ["tests"]
addopts = "-m 'not integration'"   # интеграционные тесты отключены по умолчанию
markers = [
    "integration: marks tests as integration tests (require running infrastructure)",
]
```

**Структура каталога:**

```
tests/
├── conftest.py              # глобальные фикстуры (контейнеры, клиенты)
├── unit/                    # юнит-тесты без I/O
│   └── services/
│       └── test_user_service.py
└── integration/             # тесты с реальной инфраструктурой
    ├── conftest.py          # testcontainers: Postgres, Redis, RabbitMQ
    └── repository/
        └── test_user_repository.py
```

### 7.2 Юнит-тесты

- Тестируют **только domain entities и services**.
- Репозитории — mock через `unittest.mock.AsyncMock`.
- Никаких реальных соединений, никаких `testcontainers`.
- Именование: `test_<метод>_<условие>_<ожидаемый результат>`.

```python
# tests/unit/services/test_user_service.py
from __future__ import annotations
from unittest.mock import AsyncMock
import pytest
from src.core.exceptions import ConflictError
from src.domain.entities.user import UserEntity
from src.services.user_service import UserService

async def test_create_raises_conflict_when_email_exists() -> None:
    repo = AsyncMock()
    repo.find_by_email.return_value = UserEntity(name="existing", email="a@b.com")
    service = UserService(repo=repo)

    with pytest.raises(ConflictError):
        await service.create(UserEntity(name="new", email="a@b.com"))
```

### 7.3 Интеграционные тесты

- Используют `testcontainers` — реальные Postgres / Redis / RabbitMQ в Docker.
- Обязательный маркер `@pytest.mark.integration`.
- Запускаются явно: `pytest -m integration`.
- Фикстуры с контейнерами — в `tests/integration/conftest.py`, scope=`"session"`.

```python
# tests/integration/conftest.py
from __future__ import annotations
import pytest
from testcontainers.postgres import PostgresContainer
from src.infrastructure.repository.postgresql.client.connection import PostgresConnectionPool

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16") as pg:
        yield pg

@pytest.fixture(scope="session")
async def postgres_pool(postgres_container: PostgresContainer) -> PostgresConnectionPool:
    pool = PostgresConnectionPool(
        user=postgres_container.username,
        password=postgres_container.password,
        host=postgres_container.get_container_host_ip(),
        port=int(postgres_container.get_exposed_port(5432)),
        database=postgres_container.dbname,
    )
    await pool.connect()
    yield pool
    await pool.close()
```

```python
# tests/integration/repository/test_user_repository.py
from __future__ import annotations
import pytest
from src.domain.entities.user import UserEntity
from src.infrastructure.repository.postgresql.user_repository import PostgresUserRepository
from src.infrastructure.repository.postgresql.client.connection import PostgresConnectionPool
from src.infrastructure.repository.postgresql.client.query_executor import PostgresQueryExecutor

@pytest.mark.integration
async def test_save_and_find_user(postgres_pool: PostgresConnectionPool) -> None:
    executor = PostgresQueryExecutor(connection_pool=postgres_pool)
    repo = PostgresUserRepository(executor=executor)
    entity = UserEntity(name="Ivan", email="ivan@example.com")

    saved = await repo.save(entity)
    found = await repo.find_by_id(saved.id)

    assert found is not None
    assert found.email == "ivan@example.com"
```

---

## 8. Миграции (yoyo)

### 8.1 Конфигурация

```ini
# yoyo.ini
[DEFAULT]
sources = migrations
migration_table = _yoyo_migration
batch_mode = off
verbosity = 0
```

### 8.2 Именование файлов

Формат: `<порядковый_номер>_<snake_case_описание>.py`

```
migrations/
├── 0001_create_users_table.py
├── 0002_add_email_index.py
└── 0003_create_orders_table.py
```

Номера — 4 цифры с ведущими нулями. Описание — только строчные буквы и подчёркивания.

### 8.3 Структура файла миграции

```python
from yoyo import step

__depends__ = {"0001_create_users_table"}

steps = [
    step(
        # apply
        """
        CREATE TABLE orders (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id),
            amount      NUMERIC(12, 2) NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """,
        # rollback
        """
        DROP TABLE orders;
        """,
    ),
    step(
        """
        CREATE INDEX idx_orders_user_id ON orders (user_id);
        """,
        """
        DROP INDEX idx_orders_user_id;
        """,
    ),
]
```

- `__depends__` — множество имён файлов предыдущих миграций (без `.py`). Пустое множество `{}` — для первой миграции.
- Первый аргумент `step()` — apply (накат), второй — rollback (откат). Rollback обязателен.
- Один `step` = одна логическая операция. Несколько `step` в одном файле — когда операции относятся к одной фиче.

### 8.4 Запуск миграций

```bash
# Локально
docker compose --profile migrate up migrate

# В CI / вручную
yoyo apply --batch --database "postgresql://user:pass@host/db" ./migrations
```

Сервис `migrate` в `docker-compose.yml` запускается только с профилем `--profile migrate` и зависит от healthcheck сервиса `db`.

---

## 9. Инструменты разработки

### 9.1 Ruff

Линтер и форматтер. Конфиг в `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py312"
fix = true

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "ARG", "SIM", "PTH", "RET", "RUF", "PL"]
ignore = ["PLR0913", "PLR2004", "B008", "RUF003", "RUF002"]

[tool.ruff.lint.pylint]
max-args = 7    # ← методы/функции не должны иметь больше 7 аргументов
```

**Правило max-args = 7:** если конструктору нужно больше 7 аргументов — сгруппировать в отдельный объект-конфиг или использовать `*`-only параметры.

```bash
ruff check src/          # проверка
ruff format src/         # форматирование
```

### 9.2 Pyright

Статический type checker. Конфиг в `pyproject.toml`:

```toml
[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
include = ["src"]
```

`typeCheckingMode = "standard"` — строгая проверка типов. Перед коммитом обязателен:

```bash
pyright src/
```

Ошибки pyright — блокер. Код с `# type: ignore` допускается только с комментарием, объясняющим причину.

### 9.3 pre-commit

Хуки настроены в `.pre-commit-config.yaml`. Запускаются автоматически при `git commit`:

```bash
pre-commit install        # один раз после клонирования
pre-commit run --all-files  # ручной прогон
```

### 9.4 Локальный запуск

```bash
# API-сервер (с hot-reload)
docker compose up db redis rabbitmq -d
granian --interface asgi --factory --loop uvloop --reload --host 0.0.0.0 src.main:create_app

# Все тесты (без интеграционных)
pytest

# Интеграционные тесты (нужен Docker)
pytest -m integration
```

**`main.py` — только factory функция.** Granian вызывает `create_app()` с флагом `--factory`. Голый `app = FastAPI()` на модульном уровне — запрещён.

```python
# src/main.py — ПРАВИЛЬНО
def create_app() -> FastAPI:
    config = Config()
    app = FastAPI(...)
    container = Container(config)
    app.state.container = container
    return app

# НЕПРАВИЛЬНО — объект на модульном уровне
app = FastAPI()    # ← не работает с --factory, ломает тесты
```
