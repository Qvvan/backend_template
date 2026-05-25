from abc import ABC, abstractmethod


class IConsumer(ABC):
    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def register_consumers(self) -> None:
        raise NotImplementedError
