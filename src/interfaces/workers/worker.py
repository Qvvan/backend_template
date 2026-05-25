from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod


class IWorker(ABC):
    @abstractmethod
    async def start(self, stop: asyncio.Event) -> None:
        """Запустить воркер"""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """Возвращает имя воркера"""
