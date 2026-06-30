from __future__ import annotations

from abc import ABC, abstractmethod


class IConsumer(ABC):
    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError
