import asyncio
from abc import ABC, abstractmethod


class IConsumer(ABC):
    @abstractmethod
    async def start(self, stop: asyncio.Event):
        raise NotImplementedError

    @abstractmethod
    async def register_consumers(self):
        raise NotImplementedError
