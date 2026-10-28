"""Checks CLAUDE.md rules that ruff, pyright and import-linter cannot express.

    ARCH001  @dataclass outside src/domain/entities/
    ARCH002  try/except in an endpoint (src/api/v1/) or a message handler (messaging/*/handlers/)
    ARCH003  more than one service call in an endpoint or a handler method

Silence a line with `# arch: ignore` (say why in the same comment).
Usage: python -m tools.check_architecture [root]
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

IGNORE_MARKER = "# arch: ignore"
_ROUTE_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "api_route"})


@dataclass(frozen=True, slots=True)
class Violation:
    path: Path
    line: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.code} {self.message}"


def _is_domain(rel: Path) -> bool:
    return rel.parts[:3] == ("src", "domain", "entities")


def _is_endpoint(rel: Path) -> bool:
    return rel.parts[:3] == ("src", "api", "v1") and "schemas" not in rel.parts


def _is_handler(rel: Path) -> bool:
    return "messaging" in rel.parts and "handlers" in rel.parts and "schemas" not in rel.parts


def _decorator_name(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ""


def _is_route(func: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    return any(_decorator_name(d) in _ROUTE_METHODS for d in func.decorator_list)


def _service_params(func: ast.AsyncFunctionDef | ast.FunctionDef) -> set[str]:
    params = [*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs]
    names: set[str] = set()
    for arg in params:
        annotation = ast.unparse(arg.annotation) if arg.annotation else ""
        if annotation.split(".")[-1].endswith("Service"):
            names.add(arg.arg)
    return names


def _awaited_calls(func: ast.AST) -> Iterator[ast.Call]:
    for node in ast.walk(func):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            yield node.value


def _is_endpoint_service_call(call: ast.Call, services: set[str]) -> bool:
    func = call.func
    return isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in services


def _is_handler_service_call(call: ast.Call) -> bool:
    """`await self._service.method(...)` / `await self._order_service.method(...)`."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute)):
        return False
    owner = func.value
    return isinstance(owner.value, ast.Name) and owner.value.id == "self" and owner.attr.endswith("service")


def check_file(path: Path, rel: Path) -> list[Violation]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    found: list[Violation] = []

    def add(node: ast.AST, code: str, message: str) -> None:
        line = getattr(node, "lineno", 1)
        if IGNORE_MARKER not in lines[line - 1]:
            found.append(Violation(rel, line, code, message))

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and not _is_domain(rel):
            for decorator in node.decorator_list:
                if _decorator_name(decorator) == "dataclass":
                    add(decorator, "ARCH001", f"@dataclass {node.name} must live in src/domain/entities/")

        if (_is_endpoint(rel) or _is_handler(rel)) and isinstance(node, ast.Try | ast.TryStar):
            add(node, "ARCH002", "no try/except in endpoints and handlers — errors go to the exception handlers")

        if _is_endpoint(rel) and isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and _is_route(node):
            services = _service_params(node)
            calls = [c for c in _awaited_calls(node) if _is_endpoint_service_call(c, services)]
            if len(calls) > 1:
                add(node, "ARCH003", f"endpoint {node.name} calls services {len(calls)} times — exactly one allowed")

        if _is_handler(rel) and isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, ast.AsyncFunctionDef) and not method.name.startswith("_"):
                    calls = [c for c in _awaited_calls(method) if _is_handler_service_call(c)]
                    if len(calls) > 1:
                        add(method, "ARCH003", f"handler {method.name} calls services {len(calls)} times — one allowed")
    return found


def check(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted((root / "src").rglob("*.py")):
        violations.extend(check_file(path, path.relative_to(root)))
    return violations


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    violations = check(root)
    for violation in violations:
        sys.stderr.write(f"{violation}\n")
    if violations:
        sys.stderr.write(f"Found {len(violations)} architecture violation(s). Rules: CLAUDE.md, sections 2-3.\n")
        return 1
    sys.stdout.write("Architecture rules: OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
