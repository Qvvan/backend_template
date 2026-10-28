from __future__ import annotations

from pathlib import Path

from tools.check_architecture import check


def _write(root: Path, rel: str, source: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)


def _codes(root: Path) -> list[tuple[str, str]]:
    return [(str(v.path), v.code) for v in check(root)]


def test_dataclass_allowed_only_in_domain(tmp_path: Path) -> None:
    source = "from dataclasses import dataclass\n\n@dataclass\nclass A:\n    x: int\n"
    _write(tmp_path, "src/domain/entities/a.py", source)
    _write(tmp_path, "src/services/a.py", source)
    assert _codes(tmp_path) == [("src/services/a.py", "ARCH001")]


def test_try_forbidden_in_endpoints_and_handlers_only(tmp_path: Path) -> None:
    source = "async def f() -> None:\n    try:\n        pass\n    except Exception:\n        pass\n"
    _write(tmp_path, "src/api/v1/orders.py", source)
    _write(tmp_path, "src/infrastructure/messaging/rabbitmq/handlers/order_handler.py", source)
    _write(tmp_path, "src/infrastructure/messaging/rabbitmq/client.py", source)
    _write(tmp_path, "src/api/v1/schemas/order_schemas.py", source)
    assert sorted(_codes(tmp_path)) == [
        ("src/api/v1/orders.py", "ARCH002"),
        ("src/infrastructure/messaging/rabbitmq/handlers/order_handler.py", "ARCH002"),
    ]


def test_endpoint_with_two_service_calls(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/api/v1/orders.py",
        "@router.post('/')\n"
        "async def create(body: X, service: IOrderService = Depends(f), other: IUserService = Depends(g)) -> None:\n"
        "    await service.create(1)\n"
        "    await other.notify(2)\n"
        "\n"
        "@router.get('/')\n"
        "async def ok(service: IOrderService = Depends(f)) -> None:\n"
        "    await service.list()\n",
    )
    assert _codes(tmp_path) == [("src/api/v1/orders.py", "ARCH003")]


def test_handler_with_two_service_calls(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/infrastructure/messaging/kafka/handlers/order_handler.py",
        "class H:\n"
        "    async def handle(self, msg: M) -> None:\n"
        "        await self._service.a()\n"
        "        await self._billing_service.b()\n",
    )
    assert _codes(tmp_path) == [("src/infrastructure/messaging/kafka/handlers/order_handler.py", "ARCH003")]


def test_ignore_marker_silences_a_line(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/services/a.py",
        "from dataclasses import dataclass\n\n@dataclass  # arch: ignore — generated DTO\nclass A:\n    x: int\n",
    )
    assert _codes(tmp_path) == []


def test_current_project_is_clean() -> None:
    root = Path(__file__).resolve().parents[3]
    assert check(root) == []
