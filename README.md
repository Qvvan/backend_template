# backend_template

Шаблон асинхронного бэкенда на FastAPI со строгой слоистой архитектурой, где правила проверяются автоматически,
а новые фичи генерируются одной командой.

**Стек:**

- Python 3.12, FastAPI, granian, pydantic v2
- PostgreSQL: asyncpg (чистый SQL) + yoyo-миграции
<!-- [if rabbitmq] -->
- RabbitMQ: aio-pika
<!-- [endif] -->
<!-- [if kafka] -->
- Kafka: aiokafka
<!-- [endif] -->
<!-- [if redis] -->
- Redis: кэш
<!-- [endif] -->
<!-- [if minio] -->
- MinIO / S3: файлы
<!-- [endif] -->
- OpenTelemetry, Prometheus
- uv, ruff, pyright, import-linter, pytest + testcontainers

## Что внутри

- **Генератор кода.** `make feature name=order fields="title:str amount:int"` создаёт entity, репозиторий, сервис,
  схемы, CRUD-эндпоинты с пагинацией, миграцию и тесты и регистрирует всё в DI-контейнере.
- **Архитектура проверяется машиной.** Границы слоёв (import-linter), запреты из CLAUDE.md (AST-проверка),
  типы (pyright), стиль (ruff) — в `make check`, pre-commit, CI и в hook для Claude Code.
- **Отдельные процессы для API и фоновых задач** из одного образа: задачи не дублируются при нескольких
  воркерах granian.
<!-- [if messaging] -->
- **Сообщения не теряются.** Transactional outbox, идемпотентные консьюмеры (inbox), повторы и DLQ.
<!-- [endif] -->
- **Единый формат ошибок** `{status, code, comment, obj, request_id}` для всех ошибок, включая валидацию и 500.
- **Сквозной request_id**: из `X-Request-ID` во все логи запроса, плюс трейсы OpenTelemetry с `trace_id` в логах.
<!-- [if messaging] -->
- **request_id в сообщениях**: передаётся в заголовках и восстанавливается в логах консьюмера.
<!-- [endif] -->
- **`/livez`, `/readyz`, `/metrics`** в каждом процессе.
- **Тесты из коробки:** фейки, `api_client`, интеграционные тесты на настоящих контейнерах с применёнными миграциями.
<!-- [if template] -->
- **Новый проект с нужными компонентами:** copier оставляет только выбранные Redis / RabbitMQ / Kafka / MinIO.
<!-- [endif] -->

<!-- [if template] -->
## Новый проект из шаблона

```bash
uvx copier copy --trust gh:qvvan/backend_template my_service
```

Copier спросит имя проекта и какие компоненты оставить (Postgres есть всегда), затем удалит код, конфиги, тесты,
сервисы compose и зависимости остальных и обновит `uv.lock`. Обновления шаблона потом подтягиваются в проект
трёхсторонним слиянием:

```bash
uvx copier update --trust
```

`--trust` нужен, потому что после копирования запускается `tools/init_project.py`.

<!-- [endif] -->
## Быстрый старт

Нужны Docker и [uv](https://docs.astral.sh/uv/).

```bash
make up          # .env из .env.example, сборка, миграции, все процессы приложения и инфраструктура
make ps          # статус контейнеров
make logs        # логи приложения
```

- API: http://localhost:8008/docs (Swagger при `APP_DEBUG=true`), пробы `/livez`, `/readyz`, метрики `/metrics`
- Админка воркеров (scheduler): http://localhost:8009/api/v1/workers/
<!-- [if rabbitmq] -->
- RabbitMQ UI: http://localhost:15672
<!-- [endif] -->
<!-- [if redis] -->
- RedisInsight: http://localhost:8001
<!-- [endif] -->
<!-- [if minio] -->
- MinIO Console: http://localhost:9001
<!-- [endif] -->

Hot reload в контейнерах: `make watch`. Трейсы: `OTEL_ENABLED=true` в `.env` и `make up-obs`, UI Jaeger —
http://localhost:16686.

### Локальная разработка без контейнеров приложения

```bash
uv sync
make infra           # только Postgres и выбранные компоненты в Docker
make migrate
make run-api         # http://localhost:8000, hot reload
make run-scheduler   # фоновые воркеры, http://localhost:8002
```

<!-- [if messaging] -->
```bash
make run-consumer    # консьюмеры, http://localhost:8001
```

<!-- [endif] -->
`.env.example` рассчитан на запуск на хосте (`localhost` и опубликованные порты); внутри docker compose хосты
переопределяются в `docker-compose.yml`.

## Процессы

| Процесс | Фабрика | Назначение |
|---|---|---|
| api | `src.main:create_app` | HTTP API, масштабируется горизонтально |
| scheduler | `src.entrypoints.scheduler:create_scheduler_app` | фоновые воркеры и их админка; **ровно один экземпляр** |
<!-- [if messaging] -->
| consumer | `src.entrypoints.consumer:create_consumer_app` | консьюмеры брокеров, масштабируется горизонтально |
<!-- [endif] -->

Все процессы собираются из одного `Container` и одинаково отдают пробы, метрики и ошибки. Количество воркеров
granian задаётся `GRANIAN_WORKERS`.

## Генератор кода

```bash
make feature name=order fields="title:str amount:int note:str?"     # CRUD-фича во всех слоях
make worker name=cleanup interval=60                                # периодическая задача
make migration name=add_status_to_orders                            # пустая миграция с верным номером
```

<!-- [if messaging] -->
```bash
make feature name=order fields="title:str" events=1                 # + события created/updated/deleted через outbox
make consumer name=order_paid broker=rabbitmq fields="order_id:str" # идемпотентный консьюмер
```

<!-- [endif] -->
Типы полей: `str`, `int`, `float`, `bool`, `datetime`, `date`; `?` — nullable. Фича `order` даёт
`POST/GET/PUT/DELETE /api/v1/orders` с пагинацией (`limit`/`offset`), таблицу `orders`, entity с методом
`update_from`, fake-репозиторий, юнит-тесты сервиса и API и интеграционный тест репозитория. Сгенерированный код
сразу проходит все проверки (это проверяет CI). Генератор ничего не пишет, если файл уже существует.

<!-- [if messaging] -->
## События и сообщения

**Публикация.** Событие — класс `IntegrationEvent` в `src/events/` с `destination` (exchange или topic) и
`routing_key`. Если событие связано с изменением в БД, оно пишется в таблицу `outbox` в той же транзакции:

```python
async with self._uow.begin() as session:
    saved = await session.orders.save(entity)
    await session.outbox.add(OrderCreatedEvent.from_entity(saved).to_message())
```

`OutboxRelayWorker` в процессе scheduler публикует записи в брокер (`MESSAGING_PUBLISHER`), сохраняя порядок
и повторяя попытку, если брокер недоступен. Событие не потеряется, если процесс упадёт сразу после коммита.

**Потребление.** Невалидное сообщение сразу уходит в DLQ. Если обработчик падает, сообщение повторяется,
а после последней попытки уходит в DLQ с заголовками `x-error` и `x-retry-count`.
Доставка at-least-once, поэтому сгенерированные консьюмеры идемпотентны через таблицу `inbox`.

| | RabbitMQ | Kafka |
|---|---|---|
| Повторы | очереди `<queue>.retry.N` с TTL из `RABBITMQ_RETRY_DELAYS` | `KAFKA_MAX_RETRIES` с экспоненциальной задержкой |
| DLQ | `<queue>.dlq` | `<topic>.dlq` |
| Подтверждение | ack после обработки | commit offset после обработки |

<!-- [endif] -->
## Ошибки API

Любая ошибка — включая валидацию запроса, неизвестный маршрут и необработанное исключение — возвращается так:

```json
{"status": "error", "code": "NOT_FOUND", "comment": "Order with identifier '…' not found", "obj": null, "request_id": "4b59a9dc-…"}
```

Для ошибки валидации `obj` — список `{loc, msg, type}`. Тот же `request_id` есть в заголовке `X-Request-ID`
и во всех логах этого запроса. Если клиент или gateway прислал свой `X-Request-ID`, используется он.

## Наблюдаемость

- **Логи:** JSON в stdout. В каждой записи `request_id`, а при включённом трейсинге ещё `trace_id` и `span_id`.
  Запросы проб и `/metrics` не логируются.
- **`/livez`** — процесс жив; **`/readyz`** — все зависимости доступны (проверяются параллельно с таймаутом,
  при недоступности ответ 503 со статусом по каждой).
- **`/metrics`** — Prometheus (prometheus-fastapi-instrumentator). При `GRANIAN_WORKERS > 1` у каждого процесса
  свой реестр метрик.
- **Трейсы:** `OTEL_ENABLED=true` включает OpenTelemetry: спаны HTTP-запросов, SQL и клиентов брокеров и кэша
  уходят по OTLP/HTTP на `OTEL_EXPORTER_OTLP_ENDPOINT`; контекст трейса передаётся через сообщения.

## Тесты

```bash
make test               # юнит-тесты, без Docker
make test-integration   # testcontainers: Postgres с применёнными миграциями и остальные компоненты
make test-cov           # покрытие
```

- `tests/factories.make_config()` создаёт конфиг без переменных окружения.
- Фикстура `api_client` поднимает настоящее приложение; сервис подменяется через
  `api_app.dependency_overrides[get_<name>_service]`.
- В `tests/fakes/` лежат in-memory реализации интерфейсов (UoW, репозитории, publisher, кэш).
- Фикстура `db_executor` открывает транзакцию и откатывает её после теста.

## Качество кода

```bash
make check   # ruff, format, pyright, import-linter, архитектурные правила, юнит-тесты — то же, что в CI
make fix     # автоисправление и форматирование
make pre-commit-install
```

Что проверяется автоматически: границы слоёв (import-linter, `pyproject.toml`); `@dataclass` только в domain,
отсутствие `try/except` в эндпоинтах и хендлерах, ровно один вызов сервиса (`tools/check_architecture.py`);
типы без голых `list`/`dict` (pyright); `print`, f-строки в логах, обязательные возвращаемые типы и
`from __future__ import annotations` (ruff). Полный список правил — в [CLAUDE.md](CLAUDE.md).

**CI** (`.github/workflows/ci.yml`) прогоняет линтеры и архитектуру, юнит- и интеграционные тесты, сборку образа
и отдельный job, который генерирует код генератором и проверяет результат.
<!-- [if template] -->
Ещё один job создаёт через copier пять вариантов проекта (все компоненты, только Postgres, только RabbitMQ,
только Kafka, Redis + MinIO) и проверяет каждый.
<!-- [endif] -->

## Работа с Claude Code

- `CLAUDE.md` — правила проекта.
- Скиллы в `.claude/skills/` описывают, как добавлять код через генератор (фича, воркер, миграция и т. д.).
- Hook `.claude/hooks/python-quality.sh` после каждой правки `.py` запускает ruff с автоисправлением, pyright
  и архитектурные правила и сразу возвращает ошибки.
- Агенты `.claude/agents/` — ревью архитектуры, планирование и выполнение рефакторинга.

## Конфигурация

Все настройки задаются переменными окружения, полный список с комментариями — в `.env.example`. Настройки
читаются из окружения и из `.env`; значение из окружения важнее.

| Префикс | Что настраивает |
|---|---|
| `APP_*`, `LOG_LEVEL` | режим отладки (Swagger), CORS, уровень логов |
| `POSTGRES_*` | подключение и размер пула |
<!-- [if redis] -->
| `REDIS_*` | подключение к Redis |
<!-- [endif] -->
<!-- [if rabbitmq] -->
| `RABBITMQ_*` | подключение, prefetch, задержки повторов |
<!-- [endif] -->
<!-- [if kafka] -->
| `KAFKA_*` | подключение, SASL, число и задержка повторов |
<!-- [endif] -->
<!-- [if minio] -->
| `MINIO_*` | подключение к MinIO / S3 |
<!-- [endif] -->
<!-- [if messaging] -->
| `MESSAGING_*` | брокер для публикации событий, размер пачки и интервал outbox |
<!-- [endif] -->
| `OTEL_*` | трейсинг: включение, имя сервиса, адрес коллектора |
| `GRANIAN_*` | число воркеров и другие параметры сервера |

<!-- [if template] -->
## Поддержка шаблона

Шаблон — обычный рабочий проект со всеми компонентами. При создании проекта `tools/init_project.py`:

1. удаляет файлы невыбранных компонентов (таблица `REMOVE` в скрипте);
2. обрабатывает регионы — пары строк-комментариев `[if <выражение>]` … `[endif]` (`#` в коде и конфигах,
   HTML-комментарий в Markdown); регион `[ifc <выражение>]` содержит закомментированную альтернативу, которая
   раскомментируется для своего варианта. В выражениях доступны имена `redis`, `rabbitmq`, `kafka`, `minio`,
   `messaging` (= rabbitmq or kafka) и `template`. Маркер должен стоять на отдельной строке;
3. заменяет `backend_template` на имя проекта, обновляет `uv.lock` и прогоняет ruff.

Когда добавляешь код, специфичный для компонента, оберни его в регион, а новые файлы компонента добавь в `REMOVE`.
Тест `tests/unit/tools/test_init_project.py` проверяет баланс регионов, а CI-job `copier` — все варианты проекта.

<!-- [endif] -->
