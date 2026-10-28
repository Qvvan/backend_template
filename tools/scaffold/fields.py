from __future__ import annotations

import keyword
import re
from dataclasses import dataclass

from tools.scaffold.naming import ScaffoldError

_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
RESERVED = frozenset({"id", "created_at", "updated_at", "message_id", "event_id", "occurred_at"})


@dataclass(frozen=True, slots=True)
class FieldType:
    python: str
    sql: str
    sample: str  # Python expression for tests
    sample_alt: str  # a different value, for update tests
    json_sample: str  # Python expression of the JSON value sent to the API
    comparable_in_json: bool  # response JSON equals the request JSON for this type
    compare: str = "=="  # operator for asserts in generated tests


TYPES: dict[str, FieldType] = {
    "str": FieldType("str", "TEXT", '"text"', '"changed"', '"text"', True),
    "int": FieldType("int", "BIGINT", "1", "2", "1", True),
    "float": FieldType("float", "DOUBLE PRECISION", "1.5", "2.5", "1.5", True),
    "bool": FieldType("bool", "BOOLEAN", "True", "False", "True", True, compare="is"),
    "datetime": FieldType(
        "datetime",
        "TIMESTAMPTZ",
        "datetime(2024, 1, 1, tzinfo=UTC)",
        "datetime(2024, 2, 1, tzinfo=UTC)",
        '"2024-01-01T00:00:00Z"',
        False,
    ),
    "date": FieldType("date", "DATE", "date(2024, 1, 1)", "date(2024, 2, 1)", '"2024-01-01"', True),
}


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    type: FieldType
    optional: bool

    @property
    def annotation(self) -> str:
        return f"{self.type.python} | None" if self.optional else self.type.python

    @property
    def sql_column(self) -> str:
        return f"{self.name} {self.type.sql}" + ("" if self.optional else " NOT NULL")


def parse_fields(raw: str | None, default: str = "name:str") -> list[FieldSpec]:
    """`"title:str amount:int note:str?"` -> fields; `?` makes a field optional (nullable)."""
    tokens = (raw or "").replace(",", " ").split() or default.split()
    fields: list[FieldSpec] = []
    for token in tokens:
        name, sep, type_name = token.partition(":")
        type_name = type_name or "str"
        optional = type_name.endswith("?")
        type_name = type_name.rstrip("?")
        if not sep and ":" not in token:
            type_name = "str"
        if not _FIELD_NAME.match(name) or keyword.iskeyword(name):
            raise ScaffoldError(f"Invalid field name {name!r}")
        if name in RESERVED:
            raise ScaffoldError(f"Field {name!r} is added automatically, remove it from --fields")
        if type_name not in TYPES:
            raise ScaffoldError(f"Unsupported type {type_name!r} for {name!r}; use one of: {', '.join(TYPES)}")
        if any(f.name == name for f in fields):
            raise ScaffoldError(f"Duplicate field {name!r}")
        fields.append(FieldSpec(name=name, type=TYPES[type_name], optional=optional))
    return fields
