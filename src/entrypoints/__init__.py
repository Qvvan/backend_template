"""Process entrypoints (composition root): API, message consumers and background workers.

All three are ASGI apps built from the same Container, so every process gets the same middleware,
error format, health probes and /metrics. Run them as separate processes:

    granian --interface asgi --factory src.main:create_app                                   # API
    granian --interface asgi --factory src.entrypoints.consumer:create_consumer_app           # consumers
    granian --interface asgi --factory --workers 1 src.entrypoints.scheduler:create_scheduler_app  # workers
"""
