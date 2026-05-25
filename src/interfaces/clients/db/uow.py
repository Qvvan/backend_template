from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from typing import Any


class IUnitOfWork(ABC):
    @abstractmethod
    def begin(self) -> AbstractAsyncContextManager[Any]:
        raise NotImplementedError
