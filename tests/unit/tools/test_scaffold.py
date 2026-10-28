from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from tools.scaffold import generators
from tools.scaffold.fields import parse_fields
from tools.scaffold.naming import Names, ScaffoldError
from tools.scaffold.project import next_migration

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A copy of the parts of the template the generator reads and edits."""
    for directory in ("src", "tests", "migrations"):
        shutil.copytree(ROOT / directory, tmp_path / directory, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    return tmp_path


def _parses(root: Path, paths: list[str]) -> None:
    for path in paths:
        if path.endswith(".py"):
            ast.parse((root / path).read_text(), filename=path)


# ── naming and fields ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "plural", "url", "pascal"),
    [
        ("order", "orders", "orders", "Order"),
        ("order_item", "order_items", "order-items", "OrderItem"),
        ("category", "categories", "categories", "Category"),
        ("address", "addresses", "addresses", "Address"),
    ],
)
def test_names(raw: str, plural: str, url: str, pascal: str) -> None:
    names = Names.parse(raw)
    assert (names.plural, names.url, names.pascal) == (plural, url, pascal)


@pytest.mark.parametrize("raw", ["Order!", "1order", "class", "order__item", ""])
def test_invalid_names_are_rejected(raw: str) -> None:
    with pytest.raises(ScaffoldError):
        Names.parse(raw)


def test_parse_fields_types_and_optional() -> None:
    fields = parse_fields("title:str amount:int note:str? due:date")
    assert [(f.name, f.annotation, f.sql_column) for f in fields] == [
        ("title", "str", "title TEXT NOT NULL"),
        ("amount", "int", "amount BIGINT NOT NULL"),
        ("note", "str | None", "note TEXT"),
        ("due", "date", "due DATE NOT NULL"),
    ]


@pytest.mark.parametrize("raw", ["id:str", "title:uuid", "title:str title:int", "Bad:str"])
def test_invalid_fields_are_rejected(raw: str) -> None:
    with pytest.raises(ScaffoldError):
        parse_fields(raw)


def test_next_migration_numbers_and_depends(project: Path) -> None:
    assert next_migration(project, "create_orders_table") == ("0003_create_orders_table", "0002_create_inbox_table")


# ── generation ────────────────────────────────────────────────────────────────


def test_feature_creates_every_layer_and_wires_it(project: Path) -> None:
    touched = generators.feature(project, "order", "title:str amount:int", None, events=True).apply()

    _parses(project, touched)
    for path in (
        "src/domain/entities/order.py",
        "src/interfaces/repositories/order_repository.py",
        "src/infrastructure/repository/postgresql/order_repository.py",
        "src/services/order_service.py",
        "src/api/v1/orders.py",
        "src/events/order_events.py",
        "migrations/0003_create_orders_table.py",
        "tests/unit/services/test_order_service.py",
        "tests/integration/repositories/test_order_repository.py",
    ):
        assert path in touched
    assert "def orders(self)" in (project / generators.SERVICES).read_text()
    assert "def get_order_service" in (project / generators.DEPENDENCIES).read_text()
    assert "v1_router.include_router(orders_router)" in (project / generators.V1_ROUTER).read_text()
    assert "def orders(self)" in (project / generators.SESSION).read_text()
    assert "# scaffold:services" in (project / generators.SERVICES).read_text()  # marker kept for the next run


def test_consumer_registers_handler(project: Path) -> None:
    touched = generators.consumer(project, "order_paid", "rabbitmq", "order_id:str", None, None, None).apply()

    _parses(project, touched)
    consumer = (project / "src/infrastructure/messaging/rabbitmq/consumer.py").read_text()
    assert '"_order_paid_handler"' in consumer
    assert "order_paid_handler: OrderPaidHandler" in consumer
    assert 'queue_name="backend_template.order_paid"' in consumer
    assert "order_paid_handler=OrderPaidHandler(" in (project / generators.CONSUMERS).read_text()


def test_worker_is_registered(project: Path) -> None:
    generators.worker(project, "cleanup", 30).apply()
    assert "CleanupWorker(service=self._services.cleanup" in (project / generators.WORKERS).read_text()


def test_second_run_fails_without_changing_anything(project: Path) -> None:
    generators.feature(project, "order", None, None, events=False).apply()
    services_before = (project / generators.SERVICES).read_text()

    with pytest.raises(ScaffoldError):
        generators.feature(project, "order", None, None, events=False).apply()

    assert (project / generators.SERVICES).read_text() == services_before


def test_missing_marker_fails_before_writing(project: Path) -> None:
    services = project / generators.SERVICES
    services.write_text(services.read_text().replace("# scaffold:services", ""))

    with pytest.raises(ScaffoldError, match="marker"):
        generators.feature(project, "order", None, None, events=False).apply()

    assert not (project / "src/domain/entities/order.py").exists()
