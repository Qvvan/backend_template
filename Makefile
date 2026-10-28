.DEFAULT_GOAL := help
.PHONY: help env infra up up-obs watch down logs ps migrate migration \
	run-api run-consumer run-scheduler \
	lint lint-arch format format-check typecheck fix check all \
	test test-unit test-integration test-cov test-v \
	feature worker consumer pre-commit-install

COMPOSE := docker compose
GRANIAN := uv run granian --interface asgi --factory --loop uvloop --reload

help: ## Показать список команд
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2} /^## / {printf "\n\033[1m%s\033[0m\n", substr($$0, 4)}' $(MAKEFILE_LIST)

## Окружение (docker compose)

env: ## Создать .env из .env.example (если ещё нет)
	@test -f .env || (cp .env.example .env && echo "Создан .env из .env.example")

infra: env ## Поднять только инфраструктуру (Postgres, Redis, RabbitMQ, Kafka, MinIO)
	$(COMPOSE) up -d

up: env ## Поднять всё: инфраструктура + миграции + api, consumer, scheduler
	$(COMPOSE) --profile app up -d --build

up-obs: env ## То же + Jaeger (трейсы: http://localhost:16686, нужен OTEL_ENABLED=true)
	$(COMPOSE) --profile app --profile observability up -d --build

watch: env ## Поднять всё с hot reload (изменения в src/ перезапускают контейнеры)
	$(COMPOSE) --profile app watch

down: ## Остановить все контейнеры (данные в volumes сохраняются)
	$(COMPOSE) --profile app --profile observability down

logs: ## Логи приложения (api, consumer, scheduler)
	$(COMPOSE) --profile app logs -f api consumer scheduler

ps: ## Статус контейнеров
	$(COMPOSE) --profile app --profile observability ps

## База данных

migrate: env ## Применить миграции (yoyo в контейнере)
	$(COMPOSE) --profile migrate run --rm --build migrate

migration: ## Создать миграцию: make migration name=create_orders_table
	@test -n "$(name)" || (echo "Укажи имя: make migration name=create_orders_table" && exit 1)
	uv run python -m tools.scaffold migration $(name)

## Локальный запуск (инфраструктура в docker: make infra)

run-api: ## API с hot reload на http://localhost:8000
	$(GRANIAN) --port 8000 src.main:create_app

run-consumer: ## Консьюмеры RabbitMQ/Kafka с hot reload (порт 8001 для /livez)
	$(GRANIAN) --port 8001 src.entrypoints.consumer:create_consumer_app

run-scheduler: ## Фоновые воркеры с hot reload (порт 8002, админка /api/v1/workers)
	$(GRANIAN) --port 8002 --workers 1 src.entrypoints.scheduler:create_scheduler_app

## Генерация кода

feature: ## CRUD-фича: make feature name=order fields="title:str amount:int"
	@test -n "$(name)" || (echo 'Укажи имя: make feature name=order fields="title:str amount:int"' && exit 1)
	uv run python -m tools.scaffold feature $(name) --fields "$(fields)"

worker: ## Периодический воркер: make worker name=cleanup interval=60
	@test -n "$(name)" || (echo "Укажи имя: make worker name=cleanup interval=60" && exit 1)
	uv run python -m tools.scaffold worker $(name) --interval $(or $(interval),60)

consumer: ## Консьюмер: make consumer name=order_paid broker=rabbitmq fields="order_id:str"
	@test -n "$(name)" || (echo 'Укажи имя: make consumer name=order_paid broker=rabbitmq fields="order_id:str"' && exit 1)
	uv run python -m tools.scaffold consumer $(name) --broker $(or $(broker),rabbitmq) --fields "$(fields)"

## Качество кода

lint: ## Ruff: ошибки стиля и типичные баги
	uv run ruff check src/ tests/ tools/ --no-fix

lint-arch: ## Архитектурные правила: границы слоёв + запреты из CLAUDE.md
	uv run lint-imports
	uv run python -m tools.check_architecture

format: ## Отформатировать код
	uv run ruff format src/ tests/ tools/

format-check: ## Проверить форматирование без изменений
	uv run ruff format src/ tests/ tools/ --check

typecheck: ## Pyright
	uv run pyright

fix: ## Автоисправление ruff + форматирование
	uv run ruff check src/ tests/ tools/ --fix
	uv run ruff format src/ tests/ tools/

check: lint format-check typecheck lint-arch test ## Все проверки как в CI (ничего не меняет)

all: fix typecheck lint-arch test ## Исправить всё, что можно, и прогнать проверки

## Тесты

test: ## Юнит-тесты (без Docker)
	uv run pytest

test-unit: ## Только tests/unit
	uv run pytest tests/unit/

test-integration: ## Интеграционные тесты (testcontainers, нужен Docker)
	uv run pytest -m integration

test-cov: ## Юнит-тесты с покрытием
	uv run pytest --cov=src --cov-report=term-missing

test-v: ## Юнит-тесты, подробный вывод
	uv run pytest -v

pre-commit-install: ## Установить git-хуки pre-commit
	uv run pre-commit install
