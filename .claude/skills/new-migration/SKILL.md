---
name: new-migration
description: Create a database schema migration (yoyo) — add/alter/drop a column, index, constraint or table — with correct numbering and dependencies. Use when the user wants to change the database schema of an existing table.
---

# Новая миграция

## Шаги

1. Создай файл с правильным номером и `__depends__`:
   ```bash
   make migration name=add_status_to_orders
   ```
2. Заполни оба SQL: apply и **обязательный** rollback. Один `step` — одна логическая операция.
3. Если меняется таблица фичи — обнови SQL репозитория (`src/infrastructure/repository/postgresql/`), entity и
   схемы API, иначе запросы не увидят колонку.
4. Проверка: `make test-integration` — тесты сами применяют все миграции к чистому Postgres (testcontainers),
   так что синтаксис и порядок проверяются автоматически.
5. Применение: `make migrate` (docker compose). Не предполагай, что миграция применилась — проверь
   `SELECT migration_id FROM _yoyo_migration`.

Не редактируй уже применённые миграции — создавай новую.
