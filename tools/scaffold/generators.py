from __future__ import annotations

from pathlib import Path

from tools.scaffold.fields import FieldSpec, parse_fields
from tools.scaffold.naming import Names, ScaffoldError, pluralize
from tools.scaffold.project import Plan, class_has_attribute, next_migration, project_name, render

SERVICES = "src/core/container/services.py"
REPOSITORIES = "src/core/container/repositories.py"
WORKERS = "src/core/container/workers.py"
CONSUMERS = "src/core/container/consumers.py"
DEPENDENCIES = "src/api/dependencies.py"
V1_ROUTER = "src/api/v1/__init__.py"
SESSION_INTERFACE = "src/interfaces/clients/db/uow.py"
SESSION = "src/infrastructure/uow/transaction_session.py"
FAKE_UOW = "tests/fakes/uow.py"
BROKERS = ("rabbitmq", "kafka")


def _ensure_free(root: Path, path: str, class_name: str, attribute: str) -> None:
    if class_has_attribute(root, path, class_name, attribute):
        raise ScaffoldError(f"{class_name}.{attribute} already exists in {path}")


def _split(fields: list[FieldSpec]) -> dict[str, list[FieldSpec]]:
    return {
        "fields": fields,
        "required": [f for f in fields if not f.optional],
        "optional": [f for f in fields if f.optional],
    }


def _ensure_package(plan: Plan, directory: str) -> None:
    init = f"{directory}/__init__.py"
    if not (plan.root / init).exists():
        plan.create(init, "")


def feature(root: Path, name: str, fields_raw: str | None, plural: str | None, events: bool) -> Plan:
    """CRUD slice through every layer: entity -> repository -> service -> API, plus migration and tests."""
    n = Names.parse(name, plural)
    fields = parse_fields(fields_raw)
    _ensure_free(root, SERVICES, "ServiceContainer", n.plural)
    _ensure_free(root, REPOSITORIES, "RepositoryContainer", n.plural)

    columns = ", ".join(["id", *(f.name for f in fields), "created_at", "updated_at"])
    total = len(fields) + 3
    insert_placeholders = ", ".join(f"${i}" for i in range(1, total + 1))
    assignments = [f"{f.name} = ${i}" for i, f in enumerate(fields, start=2)]
    assignments.append(f"updated_at = ${len(fields) + 2}")
    migration_stem, depends_on = next_migration(root, f"create_{n.plural}_table")
    ctx = {
        "n": n,
        "events": events,
        "columns": columns,
        "insert_placeholders": insert_placeholders,
        "update_assignments": ", ".join(assignments),
        "depends": f'{{"{depends_on}"}}' if depends_on else "set()",
        **_split(fields),
    }

    plan = Plan(root)
    _feature_files(plan, n, ctx, events, migration_stem)
    _feature_wiring(plan, n, events)
    return plan


def _feature_files(plan: Plan, n: Names, ctx: dict[str, object], events: bool, migration_stem: str) -> None:
    plan.create(f"src/domain/entities/{n.snake}.py", render("feature/entity.py.jinja", **ctx))
    plan.create(
        f"src/interfaces/repositories/{n.snake}_repository.py", render("feature/repository_interface.py.jinja", **ctx)
    )
    plan.create(f"src/interfaces/services/{n.snake}_service.py", render("feature/service_interface.py.jinja", **ctx))
    repository = render("feature/repository.py.jinja", **ctx)
    plan.create(f"src/infrastructure/repository/postgresql/{n.snake}_repository.py", repository)
    plan.create(f"src/services/{n.snake}_service.py", render("feature/service.py.jinja", **ctx))
    plan.create(f"src/api/v1/schemas/{n.snake}_schemas.py", render("feature/schemas.py.jinja", **ctx))
    plan.create(f"src/api/v1/{n.plural}.py", render("feature/router.py.jinja", **ctx))
    plan.create(f"migrations/{migration_stem}.py", render("feature/migration.py.jinja", **ctx))
    if events:
        _ensure_package(plan, "src/events")
        plan.create(f"src/events/{n.snake}_events.py", render("feature/events.py.jinja", **ctx))

    plan.create(f"tests/fakes/{n.snake}_repository.py", render("feature/fake_repository.py.jinja", **ctx))
    plan.create(f"tests/unit/services/test_{n.snake}_service.py", render("feature/test_service.py.jinja", **ctx))
    _ensure_package(plan, "tests/unit/api")
    plan.create(f"tests/unit/api/test_{n.plural}_api.py", render("feature/test_api.py.jinja", **ctx))
    _ensure_package(plan, "tests/integration/repositories")
    plan.create(
        f"tests/integration/repositories/test_{n.snake}_repository.py",
        render("feature/test_repository.py.jinja", **ctx),
    )


def _feature_wiring(plan: Plan, n: Names, events: bool) -> None:
    repo_interface = f"from src.interfaces.repositories.{n.snake}_repository import I{n.pascal}Repository"
    repo_impl = (
        f"from src.infrastructure.repository.postgresql.{n.snake}_repository import Postgres{n.pascal}Repository"
    )
    plan.add_import(REPOSITORIES, repo_interface)
    plan.add_import(REPOSITORIES, repo_impl)
    plan.insert(
        REPOSITORIES,
        "# scaffold:repositories",
        f"""
        @cached_property
        def {n.plural}(self) -> I{n.pascal}Repository:
            return Postgres{n.pascal}Repository(executor=self._infra.postgresql_query_executor)

        """,
    )
    plan.add_import(SERVICES, f"from src.interfaces.services.{n.snake}_service import I{n.pascal}Service")
    plan.add_import(SERVICES, f"from src.services.{n.snake}_service import {n.pascal}Service")
    uow_arg = ", uow=self._infra.postgres_unit_of_work" if events else ""
    plan.insert(
        SERVICES,
        "# scaffold:services",
        f"""
        @cached_property
        def {n.plural}(self) -> I{n.pascal}Service:
            return {n.pascal}Service(repo=self._repos.{n.plural}{uow_arg})

        """,
    )
    plan.add_import(DEPENDENCIES, f"from src.interfaces.services.{n.snake}_service import I{n.pascal}Service")
    plan.insert(
        DEPENDENCIES,
        "# scaffold:dependencies",
        f"""
        def get_{n.snake}_service(request: Request) -> I{n.pascal}Service:
            return request.app.state.container.services.{n.plural}


        """,
    )
    plan.add_import(V1_ROUTER, f"from src.api.v1.{n.plural} import router as {n.plural}_router")
    plan.insert(V1_ROUTER, "# scaffold:v1-routers", f"v1_router.include_router({n.plural}_router)")

    # The aggregate inside a unit of work: session.<plural> (real and fake)
    plan.add_import(SESSION_INTERFACE, repo_interface)
    plan.insert(
        SESSION_INTERFACE,
        "# scaffold:session-interface",
        f"""
        @property
        @abstractmethod
        def {n.plural}(self) -> I{n.pascal}Repository:
            raise NotImplementedError

        """,
    )
    plan.add_import(SESSION, repo_interface)
    plan.add_import(SESSION, repo_impl)
    plan.insert(
        SESSION,
        "# scaffold:session-repositories",
        f"""
        @property
        def {n.plural}(self) -> I{n.pascal}Repository:
            return Postgres{n.pascal}Repository(self._tx)

        """,
    )
    plan.add_import(FAKE_UOW, repo_interface)
    plan.add_import(FAKE_UOW, f"from tests.fakes.{n.snake}_repository import InMemory{n.pascal}Repository")
    plan.insert(FAKE_UOW, "# scaffold:fake-uow-repositories", f"self.{n.plural} = InMemory{n.pascal}Repository()")
    plan.insert(
        FAKE_UOW,
        "# scaffold:fake-session-repositories",
        f"""
        @property
        def {n.plural}(self) -> I{n.pascal}Repository:
            return self._uow.{n.plural}

        """,
    )


def worker(root: Path, name: str, interval: float) -> Plan:
    n = Names.parse(name)
    _ensure_free(root, SERVICES, "ServiceContainer", n.snake)
    ctx = {"n": n, "interval": interval}
    plan = Plan(root)
    plan.create(f"src/interfaces/services/{n.snake}_service.py", render("worker/service_interface.py.jinja", **ctx))
    plan.create(f"src/services/{n.snake}_service.py", render("worker/service.py.jinja", **ctx))
    plan.create(f"src/workers/{n.snake}_worker.py", render("worker/worker.py.jinja", **ctx))
    plan.create(f"tests/unit/workers/test_{n.snake}_worker.py", render("worker/test_worker.py.jinja", **ctx))

    plan.add_import(SERVICES, f"from src.interfaces.services.{n.snake}_service import I{n.pascal}Service")
    plan.add_import(SERVICES, f"from src.services.{n.snake}_service import {n.pascal}Service")
    plan.insert(
        SERVICES,
        "# scaffold:services",
        f"""
        @cached_property
        def {n.snake}(self) -> I{n.pascal}Service:
            return {n.pascal}Service(logger=self._logger)

        """,
    )
    plan.add_import(WORKERS, f"from src.workers.{n.snake}_worker import {n.pascal}Worker")
    plan.insert(
        WORKERS,
        "# scaffold:workers",
        f"{n.pascal}Worker(service=self._services.{n.snake}, logger=self._logger, interval={interval:g}),",
    )
    return plan


def consumer(
    root: Path,
    name: str,
    broker: str,
    fields_raw: str | None,
    destination: str | None,
    routing_key: str | None,
    queue: str | None,
) -> Plan:
    """Idempotent consumer: message schema -> handler -> service (inbox) + registration."""
    if broker not in BROKERS:
        raise ScaffoldError(f"--broker must be one of: {', '.join(BROKERS)}")
    n = Names.parse(name)
    fields = parse_fields(fields_raw, default="entity_id:str")
    _ensure_free(root, SERVICES, "ServiceContainer", n.snake)
    project = project_name(root)
    key = routing_key or n.snake.replace("_", ".")
    if destination is None:
        # RabbitMQ: one exchange per aggregate (orders); Kafka: one topic per event type (order.paid)
        destination = pluralize(n.snake.split("_")[0]) if broker == "rabbitmq" else key
    ctx = {"n": n, "broker": broker, "destination": destination, "routing_key": key, **_split(fields)}

    handlers = f"src/infrastructure/messaging/{broker}/handlers"
    consumer_module = f"src/infrastructure/messaging/{broker}/consumer.py"
    plan = Plan(root)
    plan.create(f"{handlers}/schemas/{n.snake}_schemas.py", render("consumer/message.py.jinja", **ctx))
    plan.create(f"{handlers}/{n.snake}_handler.py", render("consumer/handler.py.jinja", **ctx))
    plan.create(f"src/domain/entities/{n.snake}.py", render("consumer/entity.py.jinja", **ctx))
    plan.create(f"src/interfaces/services/{n.snake}_service.py", render("consumer/service_interface.py.jinja", **ctx))
    plan.create(f"src/services/{n.snake}_service.py", render("consumer/service.py.jinja", **ctx))
    _ensure_package(plan, "tests/unit/consumers")
    plan.create(f"tests/unit/consumers/test_{n.snake}_consumer.py", render("consumer/test_consumer.py.jinja", **ctx))

    plan.add_import(SERVICES, f"from src.interfaces.services.{n.snake}_service import I{n.pascal}Service")
    plan.add_import(SERVICES, f"from src.services.{n.snake}_service import {n.pascal}Service")
    plan.insert(
        SERVICES,
        "# scaffold:services",
        f"""
        @cached_property
        def {n.snake}(self) -> I{n.pascal}Service:
            return {n.pascal}Service(uow=self._infra.postgres_unit_of_work, logger=self._logger)

        """,
    )

    handler_import = f"from src.infrastructure.messaging.{broker}.handlers.{n.snake}_handler import {n.pascal}Handler"
    plan.add_import(CONSUMERS, handler_import)
    plan.insert(
        CONSUMERS,
        f"# scaffold:{broker}-handlers",
        f"{n.snake}_handler={n.pascal}Handler(service=self._services.{n.snake}, logger=self._logger),",
    )

    consumer_class = "BackendConsumer" if broker == "rabbitmq" else "KafkaBackendConsumer"
    plan.add_import(consumer_module, handler_import)
    plan.add_import(
        consumer_module,
        f"from src.infrastructure.messaging.{broker}.handlers.schemas.{n.snake}_schemas import {n.pascal}Message",
    )
    plan.add_slot(consumer_module, consumer_class, f"_{n.snake}_handler")
    plan.insert(consumer_module, "# scaffold:consumer-params", f"{n.snake}_handler: {n.pascal}Handler,")
    plan.insert(consumer_module, "# scaffold:consumer-assignments", f"self._{n.snake}_handler = {n.snake}_handler")
    if broker == "rabbitmq":
        registration = f"""
        await self._rabbit.consume(
            queue_name="{queue or f"{project}.{n.snake}"}",
            handler=self._{n.snake}_handler.handle,
            model={n.pascal}Message,
            exchange={n.pascal}Message.destination,
            routing_key={n.pascal}Message.routing_key,
        )
        """
    else:
        registration = f"""
        await self._kafka.consume(
            topic={n.pascal}Message.destination,
            group_id="{queue or project}",
            handler=self._{n.snake}_handler.handle,
            model={n.pascal}Message,
        )
        """
    plan.insert(consumer_module, "# scaffold:consumer-registrations", registration)
    return plan


def migration(root: Path, name: str) -> Plan:
    n = Names.parse(name)
    stem, depends_on = next_migration(root, n.snake)
    plan = Plan(root)
    plan.create(
        f"migrations/{stem}.py",
        render(
            "migration/empty.py.jinja",
            title=n.title,
            depends=f'{{"{depends_on}"}}' if depends_on else "set()",
        ),
    )
    return plan
