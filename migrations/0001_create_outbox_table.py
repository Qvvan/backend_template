"""Transactional outbox: messages written together with business data, published by the outbox relay."""

from yoyo import step

__depends__ = set()

steps = [
    step(
        """
        CREATE TABLE outbox (
            id TEXT PRIMARY KEY,
            destination TEXT NOT NULL,
            routing_key TEXT NOT NULL,
            message_key TEXT,
            payload JSONB NOT NULL,
            headers JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        );
        CREATE INDEX outbox_created_at_idx ON outbox (created_at);
        """,
        "DROP TABLE outbox;",
    ),
]
