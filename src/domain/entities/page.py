from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageEntity[T]:
    """One page of a list plus the total number of items (limit/offset pagination)."""

    items: list[T]
    total: int
    limit: int
    offset: int
