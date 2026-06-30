# CLAUDE.md — Правила разработки backend_template

## Главное правило

Слова "наверное", "вроде", "обычно", "должно быть", "скорее всего" в формулировке ответа — сигнал stop. Не выдавай догадку за факт. Вместо этого:
1. Проверь — прочитай файл, грепни проект, поищи в документации.
2. Спроси конкретный уточняющий вопрос.
3. Явно отметь: "это предположение, требует проверки".

---

## 0. Работа с кодом и фактами

**Перед изменением:**
- Прежде чем редактировать функцию/класс/файл — прочитай его целиком (Read), не по памяти, даже если "видел раньше".
- Прежде чем использовать символ — убедись, что он существует (grep).
- Не угадывай структуру файлов, имена переменных, конфиги, пути, env. Нужны для ответа — попроси показать.
- Несколько интерпретаций задачи — назови их явно и спроси, не выбирай молча.
- На "почему X не работает" — сначала запроси логи/код/конфиг, потом диагноз. Не угадывай по симптомам.

**Неуверенность:**
- Различай явно: "я знаю" / "я предполагаю" / "это надо проверить".
- "Вероятно, дело в X, проверь Y" лучше, чем "проблема в X".
- Нет фактов в контексте (версии, текущее API) — скажи и предложи поискать.

**Запреты:**
- Не придумывай имена несуществующих файлов/функций/опций.
- Не пиши "я добавил/исправил X" без соответствующего tool call. Описывай только сделанное.
- Не извиняйся за галлюцинации задним числом — предотвращай процедурно.

**Нетривиальные изменения** (>1 файла или меняется архитектура): сначала покажи план (какие файлы, что меняется, какие контракты затронуты), дождись подтверждения, потом код.

**Команды:**
- Меняющие состояние (миграции, очистка БД, `docker compose down -v`, `rm`) — сформулируй намерение, дождись согласия.
- Только на чтение (`ls`, `ruff check`, `pytest` без БД) — без подтверждения.
- Не предполагай, что миграция применилась — проверь `yoyo list` или `SELECT` из `_yoyo_migration`.
- Не предполагай состояние контейнеров — `docker compose ps` перед действием.

**Коммиты:**
- Описывай только реально сделанное. Не приписывай ("улучшил производительность", если не измерял).
- Без emoji. Первая строка: `<type>(<scope>): <imperative description>`, ≤72 символа. Типы: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `build`, `ci`.
- В теле — что изменено и почему, без хвалебных формулировок.

**Внешние библиотеки:**
- Проверяй, что функция/класс существуют в установленной версии — сигнатура могла измениться.
- Версии — в `pyproject.toml`, не предполагай.
- Не уверен в API (`asyncpg`, `aio-pika`, `pydantic v2`, `fastapi`, `granian`) — скажи "надо проверить документацию X".
- Особо осторожно после смены major: pydantic 1→2, aio-pika 8→9.

**Модификация кода:**
- Не переписывай файл целиком ради одной функции — точечные правки.
- Не меняй стиль/форматирование/импорты "заодно" с логикой — маскирует diff.
- Не удаляй непонятные комментарии — спроси.
- Не меняй сигнатуры публичных интерфейсов (`src/interfaces/`) без согласования — это контракт.

**Язык:** код, идентификаторы, комментарии, логи, сообщения исключений — английский. Коммуникация с пользователем — русский. Не смешивать в одной строке.

---

## 1. Структура проекта

```
backend_template/
├── src/
│   ├── main.py                              # Точка входа — только app factory
│   ├── api/                                 # Presentation layer
│   │   ├── __init__.py                      # Агрегация роутеров
│   │   ├── dependencies.py                  # FastAPI DI-функции
│   │   ├── exception_handlers.py            # Единственное место перехвата ошибок
│   │   ├── health.py                        # Health-check endpoints
│   │   ├── middleware/request_logging.py    # Request ID, логирование запросов
│   │   └── v1/
│   │       ├── __init__.py                  # v1_router
│   │       └── schemas/                     # Pydantic схемы запросов/ответов
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
│   ├── domain/entities/                     # Все dataclass-модели и бизнес-логика
│   ├── infrastructure/
│   │   ├── http/                            # HTTP-клиенты
│   │   ├── messaging/
│   │   │   ├── consumer.py                  # BackendConsumer — маршрутизация очередей
│   │   │   ├── publisher.py                 # MessagePublisher
│   │   │   ├── rabbitmq.py                  # RabbitMQClient — транспорт
│   │   │   └── handlers/                    # Хендлеры (schemas/ + <name>_handler.py)
│   │   ├── repository/
│   │   │   ├── postgresql/client/           # connection, query_executor, transaction_executor
│   │   │   └── redis/                       # client.py (RedisDB), repository.py (RedisRepository)
│   │   └── uow/                             # postgres_uow.py, transaction_session.py
│   ├── interfaces/                          # Абстракции — только ABC / Protocol
│   │   ├── clients/                         # cache_client/, db/
│   │   ├── messaging/                       # client, consumer, publisher
│   │   ├── repositories/                    # по одному на агрегат
│   │   ├── services/
│   │   └── workers/worker.py                # IWorker
│   ├── services/                            # Application layer — оркестрация
│   ├── utils/                               # Утилиты без бизнес-логики
│   └── workers/scheduler.py                 # AsyncScheduler
├── migrations/                              # yoyo SQL-миграции
├── Dockerfile, docker-compose.yml, pyproject.toml, yoyo.ini
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

### 2.1 ENDPOINTS (`src/api/v1/`)

- Принимает запрос **только через Pydantic схему** из `api/v1/schemas/`.
- Маппит схему в доменную модель (`@dataclass` из `domain/entities/`).
- Вызывает **ровно один** сервис. Маппит результат обратно в response-схему.
- **Без бизнес-логики, без `try/except`** (ошибки ловит только exception_handler).
- Зависимости — через `Depends()` из `api/dependencies.py`.

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

```python
# ЗАПРЕЩЕНО — бизнес-логика и работа с БД в эндпоинте
@router.post("/users/")
async def create_user(body: CreateUserRequest, db = Depends(get_postgres_db)):
    user = await db.fetchrow("SELECT * FROM users WHERE email = $1", body.email)
    if user:
        raise HTTPException(400, "already exists")   # ← бизнес-логика здесь
```

> `api/v1/schemas/` пока пуста. При добавлении эндпоинта схемы создаются здесь.

### 2.2 CONSUMERS / HANDLERS (`src/infrastructure/messaging/handlers/`)

- `consumer.py` (BackendConsumer) — только регистрирует очереди и маршрутизирует. Никакой логики.
- Для каждой очереди — **обязательная Pydantic схема** в `handlers/schemas/`.
- Хендлер: парсит сообщение через схему → маппит в `@dataclass` → вызывает **ровно один** сервис.
- Логирует только начало и завершение обработки. **Без `try/except`, без бизнес-логики.**
- RabbitMQClient передаёт в хендлер уже валидированный объект, **не dict** — повторная валидация запрещена.

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
# Регистрация в consumer.py
await self._rabbit.consume(
    queue_name="user.created",
    handler=handler.handle_user_created,
    model=UserCreatedMessage,
    exchange="users",
    routing_key="user.created",
)
```

### 2.3 SERVICES (`src/services/`)

- Знают **последовательность операций**. Зависят только от интерфейсов (`interfaces/`).
- Поднимают **доменные исключения** из `core/exceptions.py`.
- Делегируют бизнес-логику в методы `entity`. Сами логику не содержат.
- **Никогда не получают `Config`.**
- `IUnitOfWork.begin()` — **только** когда одна операция мутирует **несколько таблиц** атомарно. Запись в одну таблицу или чтение — репозиторий напрямую, без UoW.

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

```python
# ЗАПРЕЩЕНО — конфиг в сервисе, валидация вместо entity
class UserService:
    def __init__(self, config: Config, ...):   # ← конфиг запрещён
        ...
    async def create(self, entity: UserEntity) -> UserEntity:
        if "@" not in entity.email:             # ← должно быть в entity
            raise ValidationError("bad email")
```

### 2.4 DOMAIN ENTITIES (`src/domain/entities/`)

- **Только чистая бизнес-логика.** Никакого I/O, никаких внешних зависимостей.
- **Все `@dataclass` определяются только здесь.** Нигде больше.
- Никаких исключений, никакой обработки ошибок, никаких импортов из `infrastructure`/`services`/`api`.

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

    def is_valid_email(self) -> bool:
        return "@" in self.email and "." in self.email.split("@")[-1]
```

> `domain/entities/` пока пуста. Все новые `@dataclass` — здесь.

### 2.5 REPOSITORIES (`src/infrastructure/repository/`)

- Знают только **SQL-запросы**. Принимают `IQueryExecutor` или `PostgresTransactionExecutor`.
- Запрос → `query_executor` → маппинг в `@dataclass` из `domain/entities/` → возврат.
- **Никакой бизнес-логики, никакой обработки ошибок.** Интерфейс — в `interfaces/repositories/`.
- Один репозиторий = один агрегат.

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

```python
# ЗАПРЕЩЕНО — фильтрация (бизнес-логика) и обработка ошибок в репозитории
async def find_active_users(self) -> list[UserEntity]:
    rows = await self._executor.fetch("SELECT * FROM users")
    return [u for u in rows if u["is_active"]]   # ← фильтрация = бизнес-логика
# UniqueViolation → ConflictError — это задача сервиса, не репозитория
```

### 2.6 WORKERS (`src/workers/`, `src/interfaces/workers/`)

- Реализуют `IWorker`. `start(stop: asyncio.Event)` — единственная точка входа.
- Вызывают **один сервис** по расписанию/триггеру. Логируют старт, стоп, причину остановки.
- **Никакой бизнес-логики, никакого прямого обращения к БД/кэшу, никакого `Config`.**
- Регистрируются в `WorkerContainer`, передаются в `AsyncScheduler` (`start()` запускает как Tasks, `shutdown()` — graceful с таймаутом 30 сек).

```python
# src/workers/cleanup_worker.py
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

### 2.7 COMPOSITION ROOT (`src/core/container/`, `src/main.py`)

- **Единственное место, где используется `Config`.** Конфиг не передаётся ни в один слой.
- Зависимости собираются через `cached_property`. `close()` закрывает соединение только если оно открыто (проверка `"name" in self.__dict__`).

**Config (`src/core/config.py`):**
- Все секции — `frozen=True` (защита от мутации в рантайме).
- Секреты — только `SecretStr`; значение — `.get_secret_value()`. Нельзя передавать `SecretStr` в строку/SQL напрямую.
- Чтение из env через `SettingsConfigDict(env_prefix=..., frozen=True)`. Никакого `os.getenv()` вне `config.py`.

```python
# ПРАВИЛЬНО
class PostgresConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", frozen=True)
    PASSWORD: SecretStr
# в контейнере — единственное место получения значения:
PostgresConnectionPool(password=self._config.postgres.PASSWORD.get_secret_value(), ...)

# ЗАПРЕЩЕНО: PASSWORD: str (утечёт в логи/repr) | os.getenv() вне config.py
```

```python
# src/core/container/__init__.py
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
# src/api/dependencies.py
def get_postgres_db(request: Request) -> IDBTransactional:
    return request.app.state.container.infra.postgres_db
```

### 2.8 EXCEPTION HANDLER (`src/api/exception_handlers.py`)

- **Единственное место** перехвата исключений на уровне presentation.
- Возвращает `ORJSONResponse` единообразной структуры.
- Новое доменное исключение **обязано** быть зарегистрировано в `register_errors()`.

```python
def register_errors(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(req: Request, exc: AppError) -> ORJSONResponse:
        return ORJSONResponse(
            status_code=exc.http_status_code,
            content={"status": "error", "code": exc.code, "comment": exc.message, "obj": None},
        )
```

Иерархия (`src/core/exceptions.py`):
```
AppError             → HTTP 500 (базовое)
├── DatabaseError    → HTTP 500
├── ValidationError  → HTTP 422
├── NotFoundError    → HTTP 404
└── ConflictError    → HTTP 409
```

### 2.9 INTERFACES (`src/interfaces/`)

- Только `ABC` / `Protocol`. Никаких конкретных классов.
- **Никаких импортов из `infrastructure`** (asyncpg, aioredis) — нарушение = дизайн-дефект.
- Интерфейсы репозиториев — `interfaces/repositories/`, сервисов — `interfaces/services/`.

| Интерфейс | Файл | Реализация |
|---|---|---|
| `IAMQPClient` | `messaging/client.py` | `RabbitMQClient` |
| `IMessagePublisher` | `messaging/publisher.py` | `MessagePublisher` |
| `IConsumer` | `messaging/consumer.py` | `BackendConsumer` |
| `ICacheDB` | `clients/cache_client/client.py` | `RedisDB` |
| `ICacheRepository` | `clients/cache_client/repository.py` | `RedisRepository` |
| `IDBTransactional` | `clients/db/connection.py` | `PostgresConnectionPool` |
| `IQueryExecutor` | `clients/db/query_executor.py` | `Postgres{Query,Transaction}Executor` |
| `IUnitOfWork` | `clients/db/uow.py` | `PostgresUnitOfWork` |
| `IWorker` | `workers/worker.py` | кастомные воркеры |

**`health_check() -> bool`** обязателен в каждом инфра-клиенте (`PostgresConnectionPool`, `RedisDB`, `RabbitMQClient`). Возвращает `True` если соединение живо, `False` при любой ошибке — без исключений наружу. Используется в `api/health.py`.

```python
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

---

## 3. Запрещено — полный список

| # | Нарушение | Где нельзя |
|---|---|---|
| 1 | `Config` за пределами `container/` и `main.py` | Везде кроме Container |
| 2 | Бизнес-логика (условия, вычисления, правила) | Endpoints, Handlers, Workers, Repositories |
| 3 | Два+ вызова сервисов в одном эндпоинте/хендлере | Endpoints, Handlers |
| 4 | `try/except` в эндпоинтах и хендлерах | Endpoints, Handlers |
| 5 | `@dataclass` вне `src/domain/entities/` | Везде кроме domain |
| 6 | Голые типы: `list`, `dict`, `Any` без параметров | Везде |
| 7 | Магические строки/числа без `Enum` | Везде |
| 8 | Зависимость от конкретного класса вместо `ABC`/`Protocol` | Services, Handlers, Workers |
| 9 | Blocking I/O (синхронные БД, файлы, HTTP) | Везде |
| 10 | Импорт infra-типов (asyncpg, aioredis) в `interfaces/` | Interfaces |
| 11 | Прямое обращение к БД/кэшу в воркере | Workers |
| 12 | Логика маршрутизации сообщений вне `consumer.py` | — |
| 13 | Отсутствие Pydantic-схемы для очереди | Handlers |
| 14 | Несколько агрегатов в одном репозитории | Repositories |
| 15 | Отсутствие `from __future__ import annotations` | Все `.py` |
| 16 | Отсутствие возвращаемого типа на методе | Все классы |
| 17 | `print()` вместо `logger.*()` | Везде |
| 18 | f-строки в аргументе `message` логгера | Везде |

---

## 4. Именование

| Сущность | Стиль | Пример |
|---|---|---|
| Файлы | `snake_case` | `query_executor.py` |
| Классы | `PascalCase` | `PostgresConnectionPool` |
| Интерфейсы | `I` + `PascalCase` | `IAMQPClient` |
| Методы / приватные | `snake_case` / `_snake_case` | `health_check()`, `_ensure_connected()` |
| Enum-константы | `UPPER_CASE` / `PascalCase` (StrEnum) | `AMQPExchangeType.Topic` |
| Контейнеры | `<Name>Container` | `InfrastructureContainer` |
| Сервисы / Репозитории | `<Name>Service` / `<Driver><Name>Repository` | `UserService`, `PostgresUserRepository` |
| Хендлеры / Воркеры | `<Name>Handler` / `<Name>Worker` | `UserMessageHandler`, `CleanupWorker` |
| Схемы req/resp/msg | `<Action><Entity>Request` / `<Entity>Response` / `<Event>Message` | `CreateUserRequest`, `UserResponse`, `UserCreatedMessage` |
| Entity / Роутеры | `<Name>Entity` / `<name>_router` | `UserEntity`, `v1_router` |

---

## 5. Ключевые паттерны кода

### 5.1 Типизация

```python
from __future__ import annotations          # обязателен в каждом файле
from collections.abc import Mapping
from typing import Any

# ПРАВИЛЬНО — параметризованные типы, явный возврат
async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None: ...
async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]: ...

# ЗАПРЕЩЕНО — нет типов, голые list/dict/Any
async def fetchrow(self, query, *args): ...
async def process(self, data: Any) -> dict: ...
```

### 5.2 `__slots__`

Все классы обязаны иметь `__slots__`, **кроме классов с `cached_property`** (дескриптор требует `__dict__`). Исключение — только контейнеры (`Infrastructure/Repository/Service/WorkerContainer`).

```python
# ПРАВИЛЬНО
class UserService(IUserService):
    __slots__ = ("_repo",)
    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

# ПРАВИЛЬНО — контейнер без __slots__
class InfrastructureContainer:
    @cached_property
    def postgres_db(self) -> PostgresConnectionPool: ...

# ЗАПРЕЩЕНО — __slots__ на классе с cached_property (сломает его); забыть __slots__ на обычном классе
```

### 5.3 Зависимости через интерфейс

```python
# ПРАВИЛЬНО — зависимость от IAMQPClient
class BackendConsumer(IConsumer):
    def __init__(self, *, rabbit: IAMQPClient, logger: AppLogger, stop: asyncio.Event) -> None:
        self._rabbit = rabbit

# ЗАПРЕЩЕНО — зависимость от конкретного RabbitMQClient
```

### 5.4 UnitOfWork

UoW нужен **только** когда одна операция мутирует несколько таблиц атомарно. `TransactionSession` хранит `IQueryExecutor` в `_tx` и отдаёт репозитории через `@property`.

```python
# ПРАВИЛЬНО — одна таблица: напрямую
async def create(self, entity: UserEntity) -> UserEntity:
    return await self._repo.save(entity)

# ПРАВИЛЬНО — две таблицы атомарно: UoW обязателен
async def place(self, order: OrderEntity) -> OrderEntity:
    async with self._uow.begin() as session:
        result = await session.orders.save(order)
        await session.inventory.decrement(order.item_id, order.qty)
        return result

# ЗАПРЕЩЕНО — UoW ради одной таблицы (избыточно) | две таблицы без транзакции (потеря при сбое)
```

### 5.5 Enum вместо магических строк

```python
from enum import StrEnum

class AMQPExchangeType(StrEnum):
    Direct = "direct"
    Fanout = "fanout"
    Topic = "topic"
    Headers = "headers"

await client.consume(exchange_type=AMQPExchangeType.Topic)   # не "topic"
```

### 5.6 Логирование

- Только методы `AppLogger` (`debug/info/warning/error/critical`), **никогда `print()`**.
- Сообщение всегда статическое; переменные — именованными полями (`**fields`), попадают в JSON отдельными ключами. **Никаких f-строк и `%s` в `message`.**
- `logger.error()` — **внутри `except`** (тогда `exc_info` подхватывается автоматически); снаружи — `warning`/`info`.
- Логируем значимые события (старт/конец, аномалии), не каждый SQL-запрос.

```python
# ПРАВИЛЬНО
self._logger.info("User created", user_id=entity.id, email=entity.email)
try:
    await self._repo.save(entity)
except Exception:
    self._logger.error("Failed to save user", user_id=entity.id)
    raise

# ЗАПРЕЩЕНО
self._logger.info(f"User {entity.id} created")     # f-строка
print(f"User {entity.id} created")                 # print
self._logger.info("User %s created", entity.id)    # позиционное форматирование
```

### 5.7 Double-check lock для lazy connect

Инфра-клиенты с ленивым подключением — `asyncio.Lock` с двойной проверкой (предотвращает race при параллельных корутинах). `_connect_lock = asyncio.Lock()` — в `__init__` и `__slots__`.

```python
# ПРАВИЛЬНО — RabbitMQClient, PostgresConnectionPool
async def _ensure_connected(self) -> None:
    if not self._channel:                   # быстрая проверка без лока
        async with self._connect_lock:
            if not self._channel:           # повторная проверка под локом
                await self.connect()

# ЗАПРЕЩЕНО — лок на каждый вызов | вообще без лока (race condition)
```

### 5.8 `asyncio.timeout()` vs `asyncio.wait_for()` (Python 3.12+)

- `asyncio.timeout()` — простой кейс, ошибка остаётся внутри блока (напр. `health_check`).
- `asyncio.wait_for()` — когда `TimeoutError` нужно поймать снаружи или применить к группе задач (напр. `AsyncScheduler.shutdown()` с таймаутом на `gather`).

### 5.9 Graceful shutdown

```python
class WorkerContainer:
    @cached_property
    def scheduler(self) -> AsyncScheduler:
        return AsyncScheduler(logger=self._logger, workers=[])

    def start(self) -> None:
        self.scheduler.start()

    async def close(self) -> None:
        await self.scheduler.shutdown()   # ждёт все воркеры, таймаут 30 сек
```

---

## 6. Порядок добавления новой фичи

Создавай снизу вверх по слоям:

1. `domain/entities/` — `@dataclass`
2. `interfaces/repositories/` — ABC репозитория
3. `interfaces/services/` — ABC сервиса
4. `infrastructure/repository/postgresql/` — реализация репозитория
5. `services/` — реализация сервиса
6. `api/v1/schemas/` — Pydantic схемы
7. `api/v1/` — эндпоинт
8. `core/container/` — регистрация в контейнере
9. `api/dependencies.py` — DI-функция

> Сейчас пусты: `domain/entities/`, `services/`, `interfaces/{repositories,services}/`, `api/v1/schemas/`, `messaging/handlers/` (+ их `schemas/`), `infrastructure/http/`.

---

## 7. Тестирование

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"                 # async-тесты без декоратора
testpaths = ["tests"]
addopts = "-m 'not integration'"      # интеграционные отключены по умолчанию
markers = ["integration: require running infrastructure"]
```

```
tests/
├── conftest.py
├── unit/services/          # без I/O, репозитории — AsyncMock
└── integration/            # testcontainers (Postgres/Redis/RabbitMQ)
    └── conftest.py         # фикстуры контейнеров, scope="session"
```

**Юнит** — только entities и services. Репозитории через `AsyncMock`. Без реальных соединений. Именование: `test_<метод>_<условие>_<результат>`.

```python
async def test_create_raises_conflict_when_email_exists() -> None:
    repo = AsyncMock()
    repo.find_by_email.return_value = UserEntity(name="existing", email="a@b.com")
    service = UserService(repo=repo)
    with pytest.raises(ConflictError):
        await service.create(UserEntity(name="new", email="a@b.com"))
```

**Интеграционные** — `testcontainers`, обязательный `@pytest.mark.integration`, запуск `pytest -m integration`. Фикстуры контейнеров — `tests/integration/conftest.py`, `scope="session"`.

```python
@pytest.mark.integration
async def test_save_and_find_user(postgres_pool: PostgresConnectionPool) -> None:
    executor = PostgresQueryExecutor(connection_pool=postgres_pool)
    repo = PostgresUserRepository(executor=executor)
    saved = await repo.save(UserEntity(name="Ivan", email="ivan@example.com"))
    found = await repo.find_by_id(saved.id)
    assert found is not None and found.email == "ivan@example.com"
```

---

## 8. Миграции (yoyo)

```ini
# yoyo.ini
[DEFAULT]
sources = migrations
migration_table = _yoyo_migration
batch_mode = off
verbosity = 0
```

**Именование:** `<NNNN>_<snake_case_описание>.py` — 4 цифры с ведущими нулями, описание строчными буквами и подчёркиваниями (`0001_create_users_table.py`).

**Структура файла:**
```python
from yoyo import step

__depends__ = {"0001_create_users_table"}   # имена предыдущих миграций без .py; первая — set()

steps = [
    step(
        "CREATE TABLE orders (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), ...);",  # apply
        "DROP TABLE orders;",                                                          # rollback (обязателен)
    ),
]
```
> Первая миграция: `__depends__ = set()`. `{}` — это пустой dict, не множество; не используй.

Первый аргумент `step()` — apply, второй — rollback (**обязателен**). Один `step` = одна логическая операция; несколько в файле — когда относятся к одной фиче.

**Запуск:**
```bash
docker compose --profile migrate up migrate                                   # локально
yoyo apply --batch --database "postgresql://user:pass@host/db" ./migrations   # вручную/CI
```
Сервис `migrate` поднимается только с `--profile migrate` и зависит от healthcheck `db`.

---

## 9. Инструменты

### Ruff (`pyproject.toml`)
```toml
[tool.ruff]
line-length = 120
target-version = "py312"
fix = true

[tool.ruff.lint]
select = ["E","W","F","I","N","UP","B","C4","ARG","SIM","PTH","RET","RUF","PL"]
ignore = ["PLR0913","PLR2004","B008","RUF003","RUF002"]   # B008 нужен для Depends() в дефолтах

[tool.ruff.lint.pylint]
max-args = 7   # >7 аргументов → группировать в конфиг-объект или *-only параметры
```
`ruff check src/` · `ruff format src/`

### Pyright (`pyproject.toml`)
```toml
[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
include = ["src"]
```
`pyright src/` обязателен перед коммитом. Ошибки — блокер. `# type: ignore` — только с комментарием-причиной.

### pre-commit
`pre-commit install` (один раз) · `pre-commit run --all-files` (ручной прогон).

### Локальный запуск
```bash
docker compose up db redis rabbitmq -d
granian --interface asgi --factory --loop uvloop --reload --host 0.0.0.0 src.main:create_app
pytest                  # без интеграционных
pytest -m integration   # с Docker
```

**`main.py` — только factory.** Granian вызывает `create_app()` с `--factory`. Голый `app = FastAPI()` на модульном уровне запрещён (ломает `--factory` и тесты).

```python
def create_app() -> FastAPI:
    config = Config()
    app = FastAPI(...)
    app.state.container = Container(config)
    return app
```