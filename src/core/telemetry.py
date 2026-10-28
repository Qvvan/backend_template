from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor
from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Probes and metrics are not traced (comma-separated regexes, matched against the URL)
_EXCLUDED_URLS = "/livez,/readyz,/metrics"


def setup_tracing(*, service_name: str, otlp_endpoint: str) -> None:
    """Send traces to an OTLP/HTTP collector (Jaeger, Tempo, OTel Collector) and instrument the clients.

    Spans cover HTTP requests, asyncpg queries, redis commands and RabbitMQ/Kafka publish/consume;
    trace context travels through message headers, so one trace spans API -> broker -> consumer.
    Idempotent: safe to call once per process.
    """
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces")))
    trace.set_tracer_provider(provider)

    for instrumentor in (AsyncPGInstrumentor(), RedisInstrumentor(), AioPikaInstrumentor(), AIOKafkaInstrumentor()):
        if not instrumentor.is_instrumented_by_opentelemetry:
            instrumentor.instrument()


def instrument_app(app: FastAPI) -> None:
    FastAPIInstrumentor.instrument_app(app, excluded_urls=_EXCLUDED_URLS)


def shutdown_tracing() -> None:
    """Flush buffered spans on process shutdown."""
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.shutdown()
