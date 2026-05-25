.PHONY: lint format typecheck test test-unit test-integration test-cov test-v check fix all pre-commit-install dev-up dev-down

# ── Dev-окружение ─────────────────────────────────────────────────────────────
dev-up:
	docker compose up -d

dev-down:
	docker compose down

# ── Pre-commit ────────────────────────────────────────────────────────────────
pre-commit-install:
	uv run pre-commit install

# ── Линтер ────────────────────────────────────────────────────────────────────
lint:
	uv run ruff check src/

# Автоисправление + форматирование
fix:
	uv run ruff check src/ --fix
	uv run ruff format src/

# Только форматирование (без lint-правил)
format:
	uv run ruff format src/

# Проверка форматирования без изменений
format-check:
	uv run ruff format src/ --check

# ── Типы ──────────────────────────────────────────────────────────────────────
typecheck:
	uv run pyright src/

# ── Тесты ─────────────────────────────────────────────────────────────────────
test:
	uv run pytest

test-unit:
	uv run pytest tests/unit/

test-integration:
	uv run pytest -m integration

test-cov:
	uv run pytest --cov=src --cov-report=term-missing

test-v:
	uv run pytest -v

# ── Всё сразу ─────────────────────────────────────────────────────────────────

# Только проверка — ничего не меняет
check:
	uv run ruff check src/
	uv run ruff format src/ --check
	uv run pyright src/
	uv run pytest

# Исправить всё + проверка типов + тесты
all:
	uv run ruff check src/ --fix
	uv run ruff format src/
	uv run pyright src/
	uv run pytest
