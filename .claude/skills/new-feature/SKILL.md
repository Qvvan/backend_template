---
name: new-feature
description: Add a new entity / resource / CRUD feature to this service (domain entity, repository, service, API endpoints, migration, tests) with the project's generator, then adapt it to the real business rules. Use when the user wants a new table, entity, resource, endpoint group or REST API for something.
---

# Новая фича (вертикальный срез)

В этом проекте фича — 9 слоёв (CLAUDE.md, раздел «Порядок добавления фичи»). Генератор создаёт их все
и регистрирует в контейнерах; руками пишется только бизнес-логика. Не создавай файлы слоёв вручную.

## Шаги

1. Уточни у пользователя, если не сказано:
   - имя сущности в единственном числе (`order`, `order_item`);
   - поля и типы: `str`, `int`, `float`, `bool`, `datetime`, `date`; `?` — nullable (`note:str?`);
   - нужны ли события другим сервисам (created/updated/deleted через outbox) → `events=1`.
   Не придумывай поля — спроси.
2. Сгенерируй:
   ```bash
   make feature name=order fields="title:str amount:int note:str?" events=1
   ```
   Неправильный автоматический plural (`person` → `persons`) — `uv run python -m tools.scaffold feature person --plural people`.
3. Получится: entity (`src/domain/entities/`), интерфейсы, Postgres-репозиторий, сервис, схемы, роутер
   `/api/v1/<plural>` (CRUD + пагинация), миграция `migrations/NNNN_create_<plural>_table.py`, fake-репозиторий,
   юнит-тесты сервиса и API, интеграционный тест репозитория.
4. Адаптируй под требования:
   - правила и вычисления — методы entity (`src/domain/entities/<name>.py`), не сервис и не роутер;
   - проверки с ошибками (`ConflictError`, `ValidationError`) — в сервисе;
   - лишние эндпоинты — удали из роутера и сервиса вместе с тестами;
   - индексы/ограничения (UNIQUE, FK) — в сгенерированной миграции до её применения.
5. `make check` (линтеры, типы, архитектура, тесты). Затем `make migrate` и `make test-integration` при запущенном Docker.

Не меняй `# scaffold:*` маркеры — по ним генератор добавляет следующие фичи.
