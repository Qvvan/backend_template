from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tools.init_project import REMOVE, InitError, init_project, process_regions

ROOT = Path(__file__).resolve().parents[3]
FLAGS = {"redis": True, "rabbitmq": False, "kafka": True, "minio": False, "messaging": True, "template": False}


def test_if_region_kept_or_removed() -> None:
    text = "a\n# [if redis]\nb\n# [endif]\n# [if rabbitmq]\nc\n# [endif]\nd\n"
    assert process_regions(text, FLAGS) == "a\nb\nd\n"


def test_ifc_region_is_uncommented_when_kept() -> None:
    text = "    # [ifc kafka and not rabbitmq]\n    # x = 1\n    #\n    # y = 2\n    # [endif]\n"
    assert process_regions(text, FLAGS) == "    x = 1\n\n    y = 2\n"


def test_ifc_region_is_removed_when_condition_is_false() -> None:
    assert process_regions("# [ifc rabbitmq]\n# x = 1\n# [endif]\n", FLAGS) == ""


def test_nested_regions() -> None:
    text = "# [if messaging]\na\n# [if rabbitmq]\nb\n# [endif]\nc\n# [endif]\n"
    assert process_regions(text, FLAGS) == "a\nc\n"


def test_markdown_markers() -> None:
    text = "<!-- [if minio] -->\nS3\n<!-- [endif] -->\nend\n"
    assert process_regions(text, FLAGS) == "end\n"


@pytest.mark.parametrize(
    "text",
    ["# [if redis]\na\n", "a\n# [endif]\n", "# [if postgres]\na\n# [endif]\n", "# [if __import__]\n# [endif]\n"],
)
def test_malformed_regions_are_rejected(text: str) -> None:
    with pytest.raises(InitError):
        process_regions(text, FLAGS)


def test_every_template_file_has_balanced_regions() -> None:
    """Catches a forgotten [endif] in the template before a project is generated from it."""
    all_on = dict.fromkeys(FLAGS, True)
    for path in ROOT.rglob("*"):
        if path.is_file() and not {".git", ".venv"} & set(path.relative_to(ROOT).parts):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if "[if" in text and path.name != "test_init_project.py":
                process_regions(text, all_on, str(path))


def test_removed_paths_exist_in_the_template() -> None:
    """A stale entry in REMOVE means a file was moved and the generated project would keep it."""
    missing = [p for _, paths in REMOVE for p in paths if not (ROOT / p).exists() and p != "copier.yml"]
    assert missing == []


def test_init_project_renames_and_prunes(tmp_path: Path) -> None:
    for directory in ("src", "migrations"):
        shutil.copytree(ROOT / directory, tmp_path / directory, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")

    init_project(tmp_path, "shop", enabled={"rabbitmq"})

    pyproject = (tmp_path / "pyproject.toml").read_text()
    assert 'name = "shop"' in pyproject
    assert '"aio-pika>=' in pyproject
    assert '"aiokafka>=' not in pyproject
    assert "[if" not in pyproject
    assert not (tmp_path / "src/infrastructure/messaging/kafka").exists()
    assert (tmp_path / "src/infrastructure/messaging/rabbitmq").exists()
    assert "KafkaConfig" not in (tmp_path / "src/core/config.py").read_text()


def test_invalid_project_name(tmp_path: Path) -> None:
    with pytest.raises(InitError):
        init_project(tmp_path, "My-Service", enabled=set())
