from __future__ import annotations

import keyword
import re
from dataclasses import dataclass

_NAME = re.compile(r"^[a-z][a-z0-9_]*[a-z0-9]$|^[a-z]$")


class ScaffoldError(Exception):
    """A user-facing error: nothing has been written when it is raised."""


def pluralize(word: str) -> str:
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    return word + "s"


def _pascal(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_"))


@dataclass(frozen=True, slots=True)
class Names:
    snake: str  # order_item
    pascal: str  # OrderItem
    plural: str  # order_items
    plural_pascal: str  # OrderItems
    title: str  # Order item
    plural_title: str  # Order items
    url: str  # order-items

    @classmethod
    def parse(cls, raw: str, plural: str | None = None) -> Names:
        snake = raw.strip().lower().replace("-", "_")
        if not _NAME.match(snake) or "__" in snake or keyword.iskeyword(snake):
            raise ScaffoldError(f"Invalid name {raw!r}: use snake_case, e.g. order or order_item")
        plural_snake = (plural or pluralize(snake)).strip().lower().replace("-", "_")
        if not _NAME.match(plural_snake):
            raise ScaffoldError(f"Invalid plural {plural!r}")
        return cls(
            snake=snake,
            pascal=_pascal(snake),
            plural=plural_snake,
            plural_pascal=_pascal(plural_snake),
            title=snake.replace("_", " ").capitalize(),
            plural_title=plural_snake.replace("_", " ").capitalize(),
            url=plural_snake.replace("_", "-"),
        )
