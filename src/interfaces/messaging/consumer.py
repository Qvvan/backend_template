from abc import ABC, abstractmethod


class IConsumer(ABC):
    @abstractmethod
    async def start(self):
        raise NotImplementedError

    @abstractmethod
    async def register_consumers(self):
        raise NotImplementedError
