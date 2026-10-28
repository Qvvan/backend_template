---
name: new-worker
description: Add a periodic background job (cleanup, sync, recalculation, polling) to this service — worker, its service and registration in the scheduler — with the project's generator. Use when the user wants something to run every N seconds/minutes in the background.
---

# Новый фоновый воркер

Воркер только вызывает сервис по расписанию (`PeriodicWorker`), вся логика — в сервисе. Воркеры работают в
отдельном процессе scheduler (`make run-scheduler`, сервис `scheduler` в compose), ровно в одном экземпляре.

## Шаги

1. Уточни имя задачи и интервал в секундах, если не сказаны.
2. Сгенерируй:
   ```bash
   make worker name=cleanup interval=60
   ```
   Создаются: `src/workers/cleanup_worker.py`, `I<Name>Service` + `<Name>Service`, регистрация в
   `ServiceContainer` и `WorkerContainer`, тест `tests/unit/workers/test_cleanup_worker.py`.
3. Реализуй `run()` в `src/services/cleanup_service.py`: нужные репозитории/клиенты добавь в `__init__` сервиса
   (через интерфейсы) и прокинь в `ServiceContainer`. Воркер не трогай.
4. Если задача должна стартовать не сразу — список `auto_start` в `src/core/container/workers.py`;
   управление в рантайме: `POST /api/v1/workers/<name>/start|stop` в процессе scheduler.
5. `make check`.
