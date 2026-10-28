from __future__ import annotations

import ast
import re
import subprocess
import sys
import textwrap
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from tools.scaffold.naming import ScaffoldError

_TEMPLATES = Path(__file__).parent / "templates"
_MIGRATION = re.compile(r"^(\d{4})_(\w+)\.py$")

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


def render(template: str, **context: Any) -> str:
    return _env.get_template(template).render(**context)


@dataclass(frozen=True, slots=True)
class Insert:
    """Insert `text` before the line `marker`, indented like the marker."""

    path: str
    marker: str
    text: str


@dataclass(frozen=True, slots=True)
class AddImport:
    path: str
    line: str


@dataclass(frozen=True, slots=True)
class AddSlot:
    path: str
    class_name: str
    slot: str


Edit = Insert | AddImport | AddSlot


@dataclass
class Plan:
    """Everything a command will change. Validated as a whole before anything is written."""

    root: Path
    new_files: dict[str, str] = field(default_factory=dict)
    edits: list[Edit] = field(default_factory=list)

    def create(self, path: str, content: str) -> None:
        self.new_files[path] = content

    def insert(self, path: str, marker: str, text: str) -> None:
        self.edits.append(Insert(path, marker, text))

    def add_import(self, path: str, line: str) -> None:
        self.edits.append(AddImport(path, line))

    def add_slot(self, path: str, class_name: str, slot: str) -> None:
        self.edits.append(AddSlot(path, class_name, slot))

    # ── apply ────────────────────────────────────────────────────────────────

    def apply(self) -> list[str]:
        """Validate, write all files, run ruff on them. Returns the touched paths."""
        for path in self.new_files:
            if (self.root / path).exists():
                raise ScaffoldError(f"{path} already exists — nothing was changed")

        edited: dict[str, str] = {}
        for edit in self.edits:
            if edit.path not in edited:
                target = self.root / edit.path
                if not target.exists():
                    raise ScaffoldError(f"{edit.path} not found — nothing was changed")
                edited[edit.path] = target.read_text(encoding="utf-8")
        for edit in [e for e in self.edits if isinstance(e, Insert)]:
            edited[edit.path] = _insert(edited[edit.path], edit)
        for edit in [e for e in self.edits if isinstance(e, AddImport)]:
            edited[edit.path] = _add_import(edited[edit.path], edit.line)
        for edit in [e for e in self.edits if isinstance(e, AddSlot)]:
            edited[edit.path] = _add_slot(edited[edit.path], edit)

        for path, content in {**self.new_files, **edited}.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        touched = sorted({*self.new_files, *edited})
        self._format([p for p in touched if p.endswith(".py")])
        return touched

    def _format(self, paths: list[str]) -> None:
        if not paths:
            return
        ruff = [sys.executable, "-m", "ruff"]
        steps = (
            ["format", "--quiet", "--force-exclude"],  # split long lines first, so E501 is not reported
            ["check", "--fix", "--quiet", "--force-exclude"],  # sort imports, drop unused ones
            ["format", "--quiet", "--force-exclude"],
        )
        for args in steps:
            result = subprocess.run([*ruff, *args, *paths], cwd=self.root, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                sys.stderr.write(result.stdout + result.stderr)


def _insert(content: str, edit: Insert) -> str:
    lines = content.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.strip() == edit.marker]
    if len(matches) != 1:
        raise ScaffoldError(f"{edit.path}: marker '{edit.marker}' must occur exactly once — nothing was changed")
    index = matches[0]
    indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
    block = textwrap.dedent(edit.text).strip("\n").splitlines()
    new_lines = [f"{indent}{line}\n" if line.strip() else "\n" for line in block]
    return "".join(lines[:index] + new_lines + lines[index:])


def _add_import(content: str, line: str) -> str:
    if line in content.splitlines():
        return content
    anchor = "from __future__ import annotations\n"
    if anchor not in content:
        return f"{line}\n{content}"
    return content.replace(anchor, f"{anchor}\n{line}\n", 1)


def _add_slot(content: str, edit: AddSlot) -> str:
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == edit.class_name):
            continue
        for stmt in node.body:
            if (
                isinstance(stmt, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__slots__" for t in stmt.targets)
                and isinstance(stmt.value, ast.Tuple)
            ):
                slots = {ast.literal_eval(element) for element in stmt.value.elts} | {edit.slot}
                new_value = "(" + ", ".join(f'"{slot}"' for slot in sorted(slots)) + ",)"
                lines = content.splitlines(keepends=True)
                start = sum(len(line) for line in lines[: stmt.value.lineno - 1]) + stmt.value.col_offset
                end = sum(len(line) for line in lines[: (stmt.value.end_lineno or 1) - 1]) + (
                    stmt.value.end_col_offset or 0
                )
                return content[:start] + new_value + content[end:]
    raise ScaffoldError(f"{edit.path}: class {edit.class_name} with a __slots__ tuple not found")


# ── project facts ─────────────────────────────────────────────────────────────


def project_name(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["name"])


def next_migration(root: Path, name: str) -> tuple[str, str | None]:
    """(file stem of the new migration, stem of the latest existing one or None)."""
    existing = sorted(
        (int(m.group(1)), path.stem)
        for path in (root / "migrations").glob("*.py")
        if (m := _MIGRATION.match(path.name))
    )
    if any(stem.split("_", 1)[1] == name for _, stem in existing):
        raise ScaffoldError(f"Migration '*_{name}.py' already exists")
    number = existing[-1][0] + 1 if existing else 1
    return f"{number:04d}_{name}", existing[-1][1] if existing else None


def class_has_attribute(root: Path, path: str, class_name: str, attribute: str) -> bool:
    tree = ast.parse((root / path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return any(
                isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and item.name == attribute
                for item in node.body
            )
    return False
