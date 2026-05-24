from abc import ABC, abstractmethod
from typing import Any


class ICacheDB(ABC):

    @property
    @abstractmethod
    def client(self) -> Any:
        ...

    @abstractmethod
    async def close(self) -> None:
        """Закрыть подключение."""
        ...
