"""Turns a copy of the template into a project with only the selected components.

Run by copier after copying (see copier.yml); can also be run by hand on a fresh clone:

    python tools/init_project.py --name my_service --redis true --rabbitmq true --kafka false --minio false

What it does:
1. Deletes files of components that were not selected (REMOVE below).
2. Processes regions in text files. A region is a pair of comment lines:
       # [if kafka and not rabbitmq]   ...   # [endif]     (<!-- [if ...] --> in Markdown)
   Lines inside are kept when the expression is true and deleted otherwise. In `# [ifc <expr>]` regions the
   content is commented out in the template and gets uncommented when kept (an alternative for a variant).
   Names in expressions: redis, rabbitmq, kafka, minio, messaging (= rabbitmq or kafka), template (False).
3. Renames `backend_template` to the project name everywhere.
4. Refreshes uv.lock (--lock) and lets ruff drop imports left unused by deleted code.

Standard library only: it runs with copier's Python before the project has a virtualenv.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

TEMPLATE_NAME = "backend_template"
COMPONENTS = ("redis", "rabbitmq", "kafka", "minio")

# condition -> paths deleted when the condition is false
REMOVE: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "redis",
        (
            "src/infrastructure/repository/redis",
            "src/interfaces/clients/cache_client",
            "tests/fakes/cache.py",
            "tests/integration/test_redis.py",
            "tests/unit/test_redis_repository.py",
        ),
    ),
    ("minio", ("src/infrastructure/storage", "src/interfaces/clients/storage")),
    (
        "rabbitmq",
        (
            "src/infrastructure/messaging/rabbitmq",
            "src/interfaces/messaging/rabbitmq",
            "tests/integration/test_rabbitmq.py",
        ),
    ),
    (
        "kafka",
        ("src/infrastructure/messaging/kafka", "src/interfaces/messaging/kafka", "tests/integration/test_kafka.py"),
    ),
    (
        "messaging",
        (
            "src/infrastructure/messaging",
            "src/interfaces/messaging",
            "src/core/events.py",
            "src/events",
            "src/domain/entities/messaging.py",
            "src/services/outbox_relay_service.py",
            "src/interfaces/services/outbox_relay_service.py",
            "src/workers/outbox_relay_worker.py",
            "src/infrastructure/repository/postgresql/outbox_repository.py",
            "src/infrastructure/repository/postgresql/inbox_repository.py",
            "src/interfaces/repositories/outbox_repository.py",
            "src/interfaces/repositories/inbox_repository.py",
            "src/core/container/consumers.py",
            "src/entrypoints/consumer.py",
            "migrations/0001_create_outbox_table.py",
            "migrations/0002_create_inbox_table.py",
            "tests/fakes/messaging.py",
            "tests/unit/test_events.py",
            "tests/unit/test_message_publisher.py",
            "tests/unit/services/test_outbox_relay_service.py",
            "tests/integration/test_outbox_inbox.py",
            "tools/scaffold/templates/consumer",
            "tools/scaffold/templates/feature/events.py.jinja",
            ".claude/skills/new-consumer",
        ),
    ),
    ("template", ("tools/init_project.py", "tests/unit/tools/test_init_project.py", "copier.yml")),
)

_SKIP_DIRS = frozenset({".git", ".venv", "node_modules", "__pycache__", ".ruff_cache", ".pytest_cache"})
# copier's answers point to the template (`_src_path`); renaming them would break `copier update`
_SKIP_FILES = frozenset({".copier-answers.yml"})
_IF = re.compile(r"^\s*(?:#|<!--)\s*\[(if|ifc) (?P<expr>[^\]]+)\]\s*(?:-->)?\s*$")
_ENDIF = re.compile(r"^\s*(?:#|<!--)\s*\[endif\]\s*(?:-->)?\s*$")
_EXPR = re.compile(r"^[a-z_ ()]+$")
_INLINE_MARKER = re.compile(r"\S.*<!--\s*\[(?:if|ifc|endif)\b|<!--\s*\[(?:if|ifc|endif)\b.*-->.*\S")


class InitError(Exception):
    pass


def evaluate(expr: str, flags: dict[str, bool]) -> bool:
    if not _EXPR.match(expr):
        raise InitError(f"invalid region expression: {expr!r}")
    names = {name for name in re.findall(r"[a-z_]+", expr) if name not in {"and", "or", "not"}}
    unknown = names - flags.keys()
    if unknown:
        raise InitError(f"unknown names in region expression {expr!r}: {sorted(unknown)}")
    return bool(eval(expr, {"__builtins__": {}}, dict(flags)))  # template-controlled, validated above


def _uncomment(line: str) -> str:
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    if stripped.startswith("# "):
        return indent + stripped[2:]
    if stripped.rstrip("\n") == "#":
        return "\n"
    return line


def process_regions(text: str, flags: dict[str, bool], source: str = "<text>") -> str:
    out: list[str] = []
    stack: list[tuple[bool, bool]] = []  # (keep, commented)
    for number, line in enumerate(text.splitlines(keepends=True), start=1):
        if match := _IF.match(line):
            keep = evaluate(match.group("expr").strip(), flags)
            stack.append((keep and all(k for k, _ in stack), match.group(1) == "ifc"))
            continue
        if _ENDIF.match(line):
            if not stack:
                raise InitError(f"{source}:{number}: [endif] without [if]")
            stack.pop()
            continue
        if _INLINE_MARKER.search(line):
            raise InitError(f"{source}:{number}: region markers must be on their own line")
        if not stack:
            out.append(line)
        elif stack[-1][0]:
            out.append(_uncomment(line) if any(commented for _, commented in stack) else line)
    if stack:
        raise InitError(f"{source}: [if] without [endif]")
    return "".join(out)


def _text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_file() and rel.name not in _SKIP_FILES and not _SKIP_DIRS.intersection(rel.parts):
            yield path


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def init_project(root: Path, name: str, enabled: set[str]) -> list[str]:
    """Returns the deleted paths."""
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        raise InitError(f"project name must be snake_case, got {name!r}")
    flags = {component: component in enabled for component in COMPONENTS}
    flags["messaging"] = flags["rabbitmq"] or flags["kafka"]
    flags["template"] = False

    deleted: list[str] = []
    for condition, paths in REMOVE:
        if evaluate(condition, flags):
            continue
        for rel in paths:
            target = root / rel
            if target.is_dir():
                shutil.rmtree(target)
                deleted.append(rel)
            elif target.exists():
                target.unlink()
                deleted.append(rel)

    for path in _text_files(root):
        text = _read(path)
        if text is None:
            continue
        new_text = process_regions(text, flags, str(path.relative_to(root))) if "[if" in text else text
        new_text = new_text.replace(TEMPLATE_NAME, name)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
    return deleted


def _run(command: list[str], root: Path) -> bool:
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return False
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
    return result.returncode == 0


def _bool(value: str) -> bool:
    if value.lower() in {"true", "yes", "1"}:
        return True
    if value.lower() in {"false", "no", "0"}:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got {value!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--name", required=True, help="snake_case project name")
    for component in COMPONENTS:
        parser.add_argument(f"--{component}", type=_bool, default=True, metavar="true|false")
    parser.add_argument("--lock", type=_bool, default=True, metavar="true|false", help="run `uv lock` afterwards")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    enabled = {component for component in COMPONENTS if getattr(args, component)}
    try:
        deleted = init_project(root, args.name, enabled)
    except InitError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    sys.stdout.write(f"Project {args.name}: {', '.join(sorted(enabled)) or 'Postgres only'}\n")
    for rel in deleted:
        sys.stdout.write(f"  removed {rel}\n")
    if args.lock and not _run(["uv", "lock"], root):
        sys.stderr.write("warning: `uv lock` failed — run it yourself before `uv sync`\n")
    ruff = ["uv", "run", "--frozen", "ruff"]
    targets = ["src", "tests", "tools"]
    fixed = _run([*ruff, "check", "--fix", "--quiet", *targets], root)  # drops imports of removed components
    formatted = _run([*ruff, "format", "--quiet", *targets], root)
    if not (fixed and formatted):
        sys.stderr.write("warning: ruff reported problems — run `make fix` and `make check`\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
