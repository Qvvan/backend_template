"""Integration events this service publishes (IntegrationEvent subclasses).

They are contracts for other services: keep them backward compatible (add optional fields, never rename
or remove). Services build them and put them into the outbox: `session.outbox.add(event.to_message())`.
"""
