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
    migrations = project / "migrations"
    shutil.rmtree(migrations)
    migrations.mkdir()
    assert next_migration(project, "first") == ("0001_first", None)
    (migrations / "0001_first.py").write_text("")
    (migrations / "0042_custom.py").write_text("")
    assert next_migration(project, "next") == ("0043_next", "0042_custom")


# ── generation ────────────────────────────────────────────────────────────────


def test_feature_creates_every_layer_and_wires_it(project: Path) -> None:
    # [if messaging]
    touched = generators.feature(project, "widget", "title:str amount:int", None, events=True).apply()
    assert "src/events/widget_events.py" in touched
    # [endif]
    # [ifc not messaging]
    # touched = generators.feature(project, "widget", "title:str amount:int", None, events=False).apply()
    # [endif]

    _parses(project, touched)
    assert any(p.startswith("migrations/") and p.endswith("_create_widgets_table.py") for p in touched)
    for path in (
        "src/domain/entities/widget.py",
        "src/interfaces/repositories/widget_repository.py",
        "src/infrastructure/repository/postgresql/widget_repository.py",
        "src/services/widget_service.py",
        "src/api/v1/widgets.py",
        "tests/unit/services/test_widget_service.py",
        "tests/integration/repositories/test_widget_repository.py",
    ):
        assert path in touched
    assert "def widgets(self)" in (project / generators.SERVICES).read_text()
    assert "def get_widget_service" in (project / generators.DEPENDENCIES).read_text()
    assert "v1_router.include_router(widgets_router)" in (project / generators.V1_ROUTER).read_text()
    assert "def widgets(self)" in (project / generators.SESSION).read_text()
    assert "# scaffold:services" in (project / generators.SERVICES).read_text()  # marker kept for the next run


# [if rabbitmq]
def test_consumer_registers_handler(project: Path) -> None:
    touched = generators.consumer(project, "widget_paid", "rabbitmq", "order_id:str", None, None, None).apply()

    _parses(project, touched)
    consumer = (project / "src/infrastructure/messaging/rabbitmq/consumer.py").read_text()
    assert '"_widget_paid_handler"' in consumer
    assert "widget_paid_handler: WidgetPaidHandler" in consumer
    assert 'queue_name="backend_template.widget_paid"' in consumer
    assert "widget_paid_handler=WidgetPaidHandler(" in (project / generators.CONSUMERS).read_text()


# [endif]


# [if kafka]
def test_kafka_consumer_registers_handler(project: Path) -> None:
    touched = generators.consumer(project, "widget_failed", "kafka", "payment_id:str", None, None, None).apply()

    _parses(project, touched)
    consumer = (project / "src/infrastructure/messaging/kafka/consumer.py").read_text()
    assert "topic=WidgetFailedMessage.destination" in consumer
    assert 'group_id="backend_template"' in consumer


# [endif]
# [ifc not messaging]
# def test_consumer_and_events_need_a_broker(project: Path) -> None:
#     with pytest.raises(ScaffoldError, match="not part of this project"):
#         generators.consumer(project, "widget_paid", "rabbitmq", None, None, None, None)
#     with pytest.raises(ScaffoldError, match="broker"):
#         generators.feature(project, "widget", None, None, events=True)
#
#
# [endif]
def test_worker_is_registered(project: Path) -> None:
    generators.worker(project, "widget_sweeper", 30).apply()
    assert "WidgetSweeperWorker(service=self._services.widget_sweeper" in (project / generators.WORKERS).read_text()


def test_second_run_fails_without_changing_anything(project: Path) -> None:
    generators.feature(project, "widget", None, None, events=False).apply()
    services_before = (project / generators.SERVICES).read_text()

    with pytest.raises(ScaffoldError):
        generators.feature(project, "widget", None, None, events=False).apply()

    assert (project / generators.SERVICES).read_text() == services_before


def test_feature_adds_imports_the_container_may_lack(project: Path) -> None:
    """In a project without Redis the repositories container has no cached_property import at all."""
    repositories = project / generators.REPOSITORIES
    repositories.write_text(repositories.read_text().replace("from functools import cached_property\n", ""))

    generators.feature(project, "widget", None, None, events=False).apply()

    assert "from functools import cached_property" in repositories.read_text()


def test_missing_marker_fails_before_writing(project: Path) -> None:
    services = project / generators.SERVICES
    services.write_text(services.read_text().replace("# scaffold:services", ""))

    with pytest.raises(ScaffoldError, match="marker"):
        generators.feature(project, "widget", None, None, events=False).apply()

    assert not (project / "src/domain/entities/widget.py").exists()
