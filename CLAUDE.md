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
│   ├── main.py                              # API-процесс: create_app(config=None, container=None)
│   ├── entrypoints/                         # Остальные процессы (composition root)
│   │   ├── app_builder.py                   # Общая сборка FastAPI: ошибки, request id, /livez, /readyz, /metrics, трейсы
<!-- [if messaging] -->
│   │   ├── consumer.py                      # create_consumer_app — консьюмеры RabbitMQ/Kafka
<!-- [endif] -->
│   │   └── scheduler.py                     # create_scheduler_app — фоновые воркеры + админка /api/v1/workers
│   ├── api/                                 # Presentation layer
│   │   ├── __init__.py                      # router с префиксом /api
│   │   ├── dependencies.py                  # FastAPI DI-функции (get_<name>_service)
│   │   ├── exception_handlers.py            # Единственное место перехвата ошибок
│   │   ├── health.py                        # /livez, /readyz
│   │   ├── schemas.py                       # ErrorResponse, health-схемы, DEFAULT/MAX_PAGE_SIZE
│   │   ├── middleware/request_logging.py    # X-Request-ID, логирование запросов (чистый ASGI)
│   │   └── v1/
│   │       ├── __init__.py                  # v1_router (# scaffold:v1-routers)
│   │       ├── workers.py                   # админка воркеров (подключается только в scheduler)
│   │       └── schemas/                     # Pydantic схемы запросов/ответов
│   ├── core/
│   │   ├── config.py                        # Pydantic BaseSettings (только здесь), читает .env
│   │   ├── exceptions.py                    # ErrorCode + иерархия доменных исключений
│   │   ├── logger.py                        # AppLogger (JSON, request_id, trace_id)
<!-- [if messaging] -->
│   │   ├── events.py                        # IntegrationEvent, MessageHeader
<!-- [endif] -->
│   │   ├── telemetry.py                     # OpenTelemetry (OTEL_ENABLED)
│   │   └── container/                       # DI-контейнеры по слоям (cached_property)
│   ├── domain/entities/                     # Все @dataclass и бизнес-логика (PageEntity, HealthReportEntity, ...)
<!-- [if messaging] -->
│   ├── events/                              # Интеграционные события этого сервиса (контракты для других)
<!-- [endif] -->
│   ├── infrastructure/
│   │   ├── http/                            # HTTP-клиенты
<!-- [if messaging] -->
│   │   ├── messaging/{rabbitmq,kafka}/      # client.py, consumer.py, publisher.py, handlers/(schemas/)
<!-- [endif] -->
│   │   ├── repository/postgresql/           # client/ (pool, executors) + репозитории агрегатов
<!-- [if redis] -->
│   │   ├── repository/redis/                # RedisDB, RedisRepository
<!-- [endif] -->
<!-- [if minio] -->
│   │   ├── storage/minio/                   # MinIOClient
<!-- [endif] -->
│   │   └── uow/                             # PostgresUnitOfWork, TransactionSession
│   ├── interfaces/                          # Только ABC / Protocol
│   ├── services/                            # Application layer
│   └── workers/                             # AsyncScheduler, PeriodicWorker, воркеры
├── migrations/                              # yoyo SQL-миграции
├── tests/                                   # unit/, integration/ (testcontainers), fakes/, factories.py
├── tools/
│   ├── scaffold/                            # Генератор кода (make feature / worker / migration ...)
│   └── check_architecture.py                # Архитектурные правила, которые не ловят линтеры
├── .claude/                                 # skills (new-feature, new-worker, ...), агенты, hook качества
├── Dockerfile, docker-compose.yml, Makefile, pyproject.toml, yoyo.ini, .github/workflows/ci.yml
```

---

## 2. Слои архитектуры

Зависимости строго сверху вниз. Нижний слой **никогда** не знает о верхнем. Границы проверяет import-linter
(контракты в `pyproject.toml`, `make lint-arch`).

```
Presentation     →  src/api/,  src/infrastructure/messaging/*/handlers/
Application      →  src/services/
Domain           →  src/domain/entities/
Infrastructure   →  src/infrastructure/
Composition Root →  src/core/container/,  src/main.py,  src/entrypoints/
```

### 2.0 Процессы

Один образ, один `Container`, три процесса — каждый ASGI-приложение с `/livez`, `/readyz`, `/metrics`:

| Процесс | Фабрика | Что делает | Масштабирование |
|---|---|---|---|
| api | `src.main:create_app` | HTTP API | горизонтально |
<!-- [if messaging] -->
| consumer | `src.entrypoints.consumer:create_consumer_app` | консьюмеры брокеров | горизонтально |
<!-- [endif] -->
| scheduler | `src.entrypoints.scheduler:create_scheduler_app` | фоновые воркеры + `/api/v1/workers` | **ровно 1 экземпляр, 1 worker granian** |

API-процесс не запускает фоновую работу. Новый воркер или консьюмер не требует правок в процессах — только
регистрацию в контейнере (генератор делает её сам).

### 2.1 ENDPOINTS (`src/api/v1/`)

- Принимает запрос **только через Pydantic схему** из `api/v1/schemas/`.
- Маппит схему в доменную модель (`@dataclass` из `domain/entities/`).
- Вызывает **ровно один** сервис. Маппит результат обратно в response-схему.
- **Без бизнес-логики, без `try/except`** (ошибки ловит только exception_handler).
- Зависимости — через `Depends()` из `api/dependencies.py`. ID в пути — `uuid.UUID` (невалидный → 422, а не 500).

```python
# src/api/v1/users.py (так генерирует `make feature`)
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    service: IUserService = Depends(get_user_service),
) -> UserResponse:
    entity = UserEntity(name=body.name, email=body.email)
    result = await service.create(entity)
    return UserResponse.model_validate(result)
```

```python
# ЗАПРЕЩЕНО — бизнес-логика и работа с БД в эндпоинте
@router.post("/users/")
async def create_user(body: CreateUserRequest, db = Depends(get_postgres_db)):
    user = await db.fetchrow("SELECT * FROM users WHERE email = $1", body.email)
    if user:
        raise HTTPException(400, "already exists")   # ← бизнес-логика здесь
```

<!-- [if messaging] -->
### 2.2 CONSUMERS / HANDLERS (`src/infrastructure/messaging/{rabbitmq,kafka}/`)

- `consumer.py` (`BackendConsumer` / `KafkaBackendConsumer`) — только регистрирует очереди/топики и маршрутизирует.
  `start()` регистрирует и возвращается, `stop()` отменяет. Никакой логики.
- Для каждой очереди — **обязательная Pydantic схема** в `handlers/schemas/` (наследник `IntegrationEvent`).
- Хендлер: схема → `@dataclass` → **ровно один** сервис. Логирует начало и конец. **Без `try/except`.**
- Клиент передаёт в хендлер уже валидированный объект — повторная валидация запрещена.
- Сервис консьюмера идемпотентен: `session.inbox.register(message_id, consumer)` в одной транзакции с изменениями
  (доставка at-least-once).

Надёжность (делает клиент, не хендлер):

| | RabbitMQ | Kafka |
|---|---|---|
| Невалидное сообщение | сразу в `<queue>.dlq` | сразу в `<topic>.dlq` |
| Исключение в хендлере | повторы через `<queue>.retry.N` (TTL = `RABBITMQ_RETRY_DELAYS`), затем `<queue>.dlq` | `KAFKA_MAX_RETRIES` повторов с экспоненциальной задержкой, затем `<topic>.dlq` |
| Подтверждение | ack после обработки | commit offset после обработки |
| Заголовки в DLQ | `x-error`, `x-retry-count` | `x-error`, `x-retry-count` |

`x-request-id` из заголовков восстанавливается в контексте логгера на время обработки.

```python
# Регистрация в rabbitmq/consumer.py (так генерирует `make consumer`)
await self._rabbit.consume(
    queue_name="backend_template.order_paid",
    handler=self._order_paid_handler.handle,
    model=OrderPaidMessage,
    exchange=OrderPaidMessage.destination,
    routing_key=OrderPaidMessage.routing_key,
)
```

### 2.2.1 Публикация событий: outbox

- Событие — наследник `IntegrationEvent` в `src/events/` с `destination` (exchange / topic) и `routing_key`.
  Это контракт для других сервисов: только добавлять опциональные поля, не переименовывать и не удалять.
- Событие, связанное с изменением в БД, публикуется **только через outbox** в той же транзакции:

```python
async with self._uow.begin() as session:
    saved = await session.orders.save(entity)
    await session.outbox.add(OrderCreatedEvent.from_entity(saved).to_message())
```

- `OutboxRelayWorker` (процесс scheduler) публикует записи (`FOR UPDATE SKIP LOCKED`, порядок сохраняется,
  при ошибке брокера — повтор на следующем тике). Брокер выбирается `MESSAGING_PUBLISHER`.
- `IMessagePublisher.publish(event)` напрямую — только для событий без изменения БД (не атомарно).
<!-- [endif] -->

### 2.3 SERVICES (`src/services/`)

- Знают **последовательность операций**. Зависят только от интерфейсов (`interfaces/`).
- Поднимают **доменные исключения** из `core/exceptions.py`.
- Делегируют бизнес-логику в методы `entity`. Сами логику не содержат.
- **Никогда не получают `Config`** (только примитивы, если нужны: `batch_size`, `interval`).
- `IUnitOfWork.begin()` — **только** когда операция мутирует **несколько таблиц** атомарно. Запись в одну таблицу
  или чтение — репозиторий напрямую.
<!-- [if messaging] -->
- Запись в БД + событие в outbox — тоже через UoW (это две таблицы).
<!-- [endif] -->

```python
class UserService(IUserService):
    __slots__ = ("_repo",)

    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

    async def create(self, entity: UserEntity) -> UserEntity:
        existing = await self._repo.find_by_email(entity.email)
        if existing:
            raise ConflictError("User with this email already exists")
        return await self._repo.save(entity)
```

### 2.4 DOMAIN ENTITIES (`src/domain/entities/`)

- **Только чистая бизнес-логика.** Никакого I/O, никаких внешних зависимостей (pydantic, драйверы — тоже нельзя).
- **Все `@dataclass` определяются только здесь.**
- Никаких исключений, никакой обработки ошибок, никаких импортов из других слоёв.
- Общие: `PageEntity[T]` (пагинация), `HealthReportEntity`.
<!-- [if messaging] -->
- `OutgoingMessage` — сериализованное событие для outbox и брокера.
<!-- [endif] -->

```python
@dataclass
class UserEntity:
    name: str
    email: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def is_valid_email(self) -> bool:
        return "@" in self.email and "." in self.email.split("@")[-1]
```

### 2.5 REPOSITORIES (`src/infrastructure/repository/`)

- Знают только **SQL-запросы**. Принимают `IQueryExecutor` (вне транзакции — `PostgresQueryExecutor`,
  внутри UoW — `PostgresTransactionExecutor` через `TransactionSession`).
- Запрос → executor → маппинг в `@dataclass` → возврат. **Никакой бизнес-логики, никакой обработки ошибок.**
- Один репозиторий = один агрегат. `json/jsonb` колонки принимают и возвращают dict (кодек в пуле),
  `uuid` — строки.
- Для работы в UoW агрегат добавляется свойством в `ITransactionSession` и `TransactionSession`
  (генератор делает это сам: `session.<plural>`).

```python
# ЗАПРЕЩЕНО — фильтрация (бизнес-логика) и обработка ошибок в репозитории
async def find_active_users(self) -> list[UserEntity]:
    rows = await self._executor.fetch("SELECT * FROM users")
    return [u for u in rows if u["is_active"]]   # ← фильтрация = бизнес-логика
```

### 2.6 WORKERS (`src/workers/`)

- Периодические воркеры наследуют `PeriodicWorker`: определяют `name` и `tick()`, где ровно один вызов сервиса.
  База сама логирует старт/стоп, ловит и логирует исключение тика, прерывает паузу по stop-событию.
- **Никакой бизнес-логики, никакого прямого обращения к БД/кэшу, никакого `Config`.**
- Регистрация — в `WorkerContainer` (`# scaffold:workers`); запускает их только процесс scheduler.

```python
class CleanupWorker(PeriodicWorker):
    __slots__ = ("_service",)

    def __init__(self, service: ICleanupService, logger: AppLogger, interval: float) -> None:
        super().__init__(logger=logger, interval=interval)
        self._service = service

    @property
    def name(self) -> str:
        return "cleanup"

    async def tick(self) -> None:
        await self._service.run()
```

### 2.7 COMPOSITION ROOT (`src/core/container/`, `src/main.py`, `src/entrypoints/`)

- **Единственное место, где используется `Config`.** Конфиг не передаётся ни в один слой.
- Зависимости собираются через `cached_property`. `close()` закрывает только созданное (`"name" in self.__dict__`).
- Фабрики процессов принимают `(config, container)` — тесты подменяют их целиком.
- Маркеры `# scaffold:<name>` — места, куда генератор вставляет код. Не удалять и не дублировать.

**Config (`src/core/config.py`):**
- Все секции — `frozen=True`; секреты — только `SecretStr` (`.get_secret_value()` только в контейнере).
- Источники: переменные окружения, затем `.env` (переменные окружения важнее). Никакого `os.getenv()`.

### 2.8 ОШИБКИ API (`src/api/exception_handlers.py`)

- **Единственное место** перехвата исключений на уровне presentation. Каждый ответ с ошибкой:
  `{"status": "error", "code": ..., "comment": ..., "obj": ..., "request_id": ...}` (`ErrorResponse`).
- `AppError` → свой HTTP-статус и `ErrorCode`; ошибки валидации запроса → 422, `obj` = список
  `{loc, msg, type}`; `HTTPException` (в т.ч. 404 роутинга) → тот же формат; любое другое исключение → 500
  `INTERNAL_ERROR` без деталей (детали — в логе с тем же `request_id`).
- Новое доменное исключение наследует `AppError` и получает значение `ErrorCode`.

```
AppError             → HTTP 500 (базовое)
├── DatabaseError    → HTTP 500
├── ValidationError  → HTTP 422
├── NotFoundError    → HTTP 404
└── ConflictError    → HTTP 409
```

### 2.9 INTERFACES (`src/interfaces/`)

- Только `ABC` / `Protocol`. Никаких импортов из `infrastructure` и драйверов (import-linter).
- `health_check() -> bool` обязателен в каждом инфра-клиенте: `True`, если соединение живо, `False` при любой
  ошибке, без исключений наружу. Клиенты для `/readyz` перечислены в `ServiceContainer.health`.

---

## 3. Правила и кто их проверяет

Нарушение правил с пометкой «авто» роняет `make check`, pre-commit, CI и hook Claude после правки файла.

| # | Правило | Проверяет |
|---|---|---|
| 1 | `Config` только в composition root | авто: import-linter |
| 2 | Бизнес-логика только в entity/service | ревью |
| 3 | Ровно один вызов сервиса в эндпоинте/хендлере | авто: `ARCH003` |
| 4 | Нет `try/except` в эндпоинтах и хендлерах | авто: `ARCH002` |
| 5 | `@dataclass` только в `src/domain/entities/` | авто: `ARCH001` |
| 6 | Нет голых `list`/`dict`/`tuple` без параметров | авто: pyright `reportMissingTypeArgument` |
| 7 | Нет магических строк/чисел — `Enum`/константы | ревью |
| 8 | Зависимость от интерфейсов, не от реализаций | авто: import-linter (services, workers, api) |
| 9 | Нет blocking I/O | ревью (синхронный SDK — только через `asyncio.to_thread`) |
| 10 | Нет драйверов в `interfaces/` | авто: import-linter |
| 11 | Воркер не ходит в БД/кэш напрямую | авто: import-linter |
<!-- [if messaging] -->
| 12 | Маршрутизация сообщений только в `consumer.py` | ревью |
| 13 | Pydantic-схема для каждой очереди | ревью (генератор создаёт) |
<!-- [endif] -->
| 14 | Один агрегат на репозиторий | ревью |
| 15 | `from __future__ import annotations` в каждом модуле | авто: ruff I002 (добавляет сам) |
| 16 | Возвращаемый тип у каждой функции/метода | авто: ruff ANN20x |
| 17 | `print()` запрещён | авто: ruff T201 |
| 18 | f-строки/`%`/`.format` в сообщении лога запрещены | авто: ruff G |

Подавление — только точечно и с причиной: `# arch: ignore — <почему>`, `# noqa: <код>  # <почему>`,
`# type: ignore[код]  # <почему>`.

---

## 4. Именование

| Сущность | Стиль | Пример |
|---|---|---|
| Файлы | `snake_case` | `query_executor.py` |
| Классы | `PascalCase` | `PostgresConnectionPool` |
| Интерфейсы | `I` + `PascalCase` | `IUnitOfWork` |
| Методы / приватные | `snake_case` / `_snake_case` | `health_check()`, `_ensure_connected()` |
| Enum-константы | `UPPER_CASE` | `ErrorCode.NOT_FOUND` |
| Контейнеры | `<Name>Container` | `InfrastructureContainer` |
| Сервисы / Репозитории | `<Name>Service` / `<Driver><Name>Repository` | `UserService`, `PostgresUserRepository` |
| Хендлеры / Воркеры | `<Name>Handler` / `<Name>Worker` | `OrderPaidHandler`, `CleanupWorker` |
| Схемы req/resp/msg | `<Action><Entity>Request` / `<Entity>Response` / `<Event>Message` | `CreateUserRequest`, `UserResponse`, `OrderPaidMessage` |
| События | `<Entity><Past>Event` | `OrderCreatedEvent` |
| Entity / Роутеры | `<Name>Entity` / `<name>_router` | `UserEntity`, `v1_router` |

---

## 5. Ключевые паттерны кода

### 5.1 Типизация

```python
async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None: ...
async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]: ...
```

### 5.2 `__slots__`

Все классы обязаны иметь `__slots__`, **кроме классов с `cached_property`** (контейнеры) и pydantic-моделей.

### 5.3 Зависимости через интерфейс

```python
class OrderService(IOrderService):
    def __init__(self, repo: IOrderRepository, uow: IUnitOfWork) -> None: ...   # не PostgresOrderRepository
```

### 5.4 UnitOfWork

```python
# одна таблица — напрямую
async def create(self, entity: UserEntity) -> UserEntity:
    return await self._repo.save(entity)

# две таблицы (или запись + событие) — UoW обязателен
async def place(self, order: OrderEntity) -> OrderEntity:
    async with self._uow.begin() as session:
        result = await session.orders.save(order)
        await session.inventory.decrement(order.item_id, order.qty)
        return result
```

### 5.5 Enum вместо магических строк

```python
raise AppError("Payment provider rejected the card", code=ErrorCode.CONFLICT)
await client.consume(..., exchange_type=AMQPExchangeType.Topic)   # не "topic"
```

### 5.6 Логирование

- Только `AppLogger` (`debug/info/warning/error/critical`). Сообщение статическое, переменные — `**fields`.
- `logger.error()` — **внутри `except`** (тогда `exc_info` подхватывается сам); снаружи — `warning`/`info`.
- В каждой записи автоматически: `request_id` (HTTP `X-Request-ID` или заголовок сообщения), `trace_id`/`span_id`
  при включённом OpenTelemetry. Пробы и `/metrics` не логируются.

```python
self._logger.info("User created", user_id=entity.id)
```

### 5.7 Double-check lock для lazy connect

```python
async def _ensure_connected(self) -> None:
    if not self._channel:                   # быстрая проверка без лока
        async with self._connect_lock:
            if not self._channel:           # повторная проверка под локом
                await self.connect()
```

### 5.8 `asyncio.timeout()` vs `asyncio.wait_for()`

- `asyncio.timeout()` — простой кейс внутри блока (`health_check`).
- `asyncio.wait_for()` — когда `TimeoutError` ловится снаружи или таймаут на группу задач.

### 5.9 Graceful shutdown

Каждый процесс закрывает ресурсы в lifespan (`container.closer()`): сначала прекращается приём новой работы,
воркеры получают stop-событие (`AsyncScheduler.shutdown()`, таймаут 30 сек), затем закрываются клиенты; трейсы
досылаются (`shutdown_tracing()`).

---

## 6. Порядок добавления новой фичи

**Генератор делает все слои сразу** (и тесты, и регистрацию):

```bash
make feature name=order fields="title:str amount:int note:str?"      # CRUD, миграция, тесты
<!-- [if messaging] -->
make feature name=order fields="..." events=1                        # + события через outbox
make consumer name=order_paid broker=rabbitmq fields="order_id:str"  # идемпотентный консьюмер
<!-- [endif] -->
make worker name=cleanup interval=60                                 # периодический воркер
make migration name=add_status_to_orders                             # пустая миграция с верным номером
```

Типы полей: `str int float bool datetime date`, `?` — nullable. Ничего не пишется, если файл уже есть или маркер
не найден. После генерации: бизнес-правила — в entity, проверки — в сервисе, `make check`.

Порядок слоёв (если вручную): entity → интерфейс репозитория → интерфейс сервиса → репозиторий → сервис →
схемы → эндпоинт → контейнер → `dependencies.py` → миграция → тесты.

---

## 7. Тестирование

```
tests/
├── conftest.py            # logger, container, api_app, api_client
├── factories.py           # make_config() — Config без переменных окружения
├── fakes/                 # in-memory реализации интерфейсов: UoW, репозитории фич и др.
├── unit/                  # без I/O: сервисы, API (api_app + dependency_overrides), воркеры, tools
└── integration/           # testcontainers: Postgres (+миграции), брокеры, Redis
```

- **Юнит** — сервисы на fakes (или `AsyncMock`), API через `api_app.dependency_overrides[get_x_service]`.
  Именование: `test_<метод>_<условие>_<результат>`.
- **Интеграционные** — `pytest -m integration` (`make test-integration`), нужен Docker. Postgres-фикстура
  применяет **все** миграции из `migrations/`; `db_executor` откатывает транзакцию после каждого теста.

```python
async def test_create_raises_conflict_when_email_exists() -> None:
    repo = InMemoryUserRepository()
    await repo.save(UserEntity(name="existing", email="a@b.com"))
    with pytest.raises(ConflictError):
        await UserService(repo=repo).create(UserEntity(name="new", email="a@b.com"))
```

---

## 8. Миграции (yoyo)

- Имя: `<NNNN>_<snake_case>.py`; создавать `make migration name=...` (номер и `__depends__` проставятся сами).
- Первый аргумент `step()` — apply, второй — rollback (**обязателен**). Применённые миграции не редактировать.
- Применить: `make migrate` (docker compose) или `yoyo apply --batch --database postgresql://... ./migrations`.
- В docker compose сервис `migrate` выполняется перед стартом приложения (`make up`).

---

## 9. Инструменты

| Команда | Что делает |
|---|---|
| `make help` | Все команды |
| `make up` / `make watch` / `make down` | Весь стек в docker compose / с hot reload / остановить |
| `make run-api`, `make run-scheduler` | Процессы локально с hot reload (инфраструктура: `make infra`) |
<!-- [if messaging] -->
| `make run-consumer` | Консьюмеры локально с hot reload |
<!-- [endif] -->
| `make check` | ruff, format, pyright, import-linter, архитектурные правила, юнит-тесты — то же, что CI |
| `make fix` | Автоисправление ruff + форматирование |
| `make test-integration` | Интеграционные тесты (Docker) |

- `pyright` проверяет `src`, `tests`, `tools`; ошибки — блокер.
- pre-commit (`make pre-commit-install`) запускает те же инструменты через `uv run` — версии из `uv.lock`.
- Claude Code: после каждой правки `.py` hook `.claude/hooks/python-quality.sh` прогоняет ruff (с автофиксом),
  pyright и архитектурные правила по файлу и возвращает ошибки. Скиллы: `new-feature`, `new-worker`,
  `new-migration`.
<!-- [if messaging] -->
- Скилл `new-consumer` — консьюмер сообщений через генератор.
<!-- [endif] -->
- CI (`.github/workflows/ci.yml`): линтеры и архитектура, юнит, интеграция, генератор (генерирует код и прогоняет
  все проверки на нём), сборка образа.

**`main.py` — только factory.** Голый `app = FastAPI()` на модульном уровне запрещён (ломает `--factory` и тесты).
