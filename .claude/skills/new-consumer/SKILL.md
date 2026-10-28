---
name: new-consumer
description: Add a message consumer (RabbitMQ queue or Kafka topic) to this service — message schema, handler, idempotent service, registration and tests — using the project's generator, then implement the business logic. Use when the user wants to react to an event / message / queue / topic from another service.
---

# Новый консьюмер сообщений

Консьюмер в этом проекте — это всегда 5 частей: Pydantic-схема сообщения (`IntegrationEvent`), `@dataclass`-entity,
хендлер (маппинг схема → entity, ровно один вызов сервиса), сервис (идемпотентность через inbox в одной транзакции
с бизнес-изменениями) и регистрация очереди в `consumer.py`. Не пиши их руками — сгенерируй.

## Шаги

1. Уточни у пользователя, если не сказано: имя события (`order_paid`), брокер (`rabbitmq`/`kafka`), поля сообщения
   и их типы, откуда приходит (exchange/topic, routing key). Не угадывай имена exchange/topic — спроси.
2. Сгенерируй:
   ```bash
   make consumer name=order_paid broker=rabbitmq fields="order_id:str amount:int note:str?"
   ```
   Доп. параметры (через `uv run python -m tools.scaffold consumer ... --help`): `--destination`
   (exchange/topic), `--routing-key`, `--queue` (очередь RabbitMQ / consumer group Kafka).
3. Реализуй бизнес-логику в `src/services/<name>_service.py` на месте `TODO` — внутри уже открытой транзакции
   (`session.<repo>...`), после проверки `session.inbox.register(...)`. Хендлер и `consumer.py` не трогай.
4. Допиши тесты в `tests/unit/consumers/test_<name>_consumer.py` под реальную логику.
5. Прогони `make check`. Ошибки линтера/архитектуры чини, а не подавляй.

## Как это работает (чтобы объяснять пользователю)

- Невалидное сообщение сразу уходит в DLQ (`<queue>.dlq` / `<topic>.dlq`) с заголовком `x-error`.
- Исключение в хендлере → повторы (RabbitMQ: очереди `<queue>.retry.N` с TTL из `RABBITMQ_RETRY_DELAYS`;
  Kafka: `KAFKA_MAX_RETRIES` с экспоненциальной задержкой), затем DLQ.
- Доставка at-least-once, поэтому сервис идемпотентен через inbox.
- `x-request-id` из заголовков восстанавливается в логах обработчика.
- Консьюмеры работают в отдельном процессе: `make run-consumer` / сервис `consumer` в docker compose.
