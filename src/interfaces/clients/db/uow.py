from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, AbstractAsyncContextManager
from typing import Any


class IUnitOfWork(ABC):
    @abstractmethod
    async def begin(self) -> AbstractAsyncContextManager[Any]:
        raise NotImplementedError
