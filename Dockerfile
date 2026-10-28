FROM python:3.12.7-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Extra dependency groups, e.g. "--group migrations" for the yoyo image
ARG EXTRA_GROUP=""

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev ${EXTRA_GROUP}


FROM python:3.12.7-slim-bookworm

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GRANIAN_INTERFACE=asgi \
    GRANIAN_HOST=0.0.0.0 \
    GRANIAN_PORT=8000 \
    GRANIAN_LOOP=uvloop

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app yoyo.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app src ./src

USER app

EXPOSE 8000

# Every process (api, consumer, scheduler) serves /livez on 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/livez', timeout=2)"]

# API by default; consumer and scheduler override the command (see docker-compose.yml)
CMD ["granian", "--factory", "src.main:create_app"]
