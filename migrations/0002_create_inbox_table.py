"""Inbox: ids of messages already processed by each consumer (idempotent message handling)."""

from yoyo import step

__depends__ = {"0001_create_outbox_table"}

steps = [
    step(
        """
        CREATE TABLE inbox (
            message_id TEXT NOT NULL,
            consumer TEXT NOT NULL,
            processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (message_id, consumer)
        );
        """,
        "DROP TABLE inbox;",
    ),
]
