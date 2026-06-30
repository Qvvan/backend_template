from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict


class WorkerInfo(TypedDict):
    name: str
    running: bool
    auto_start: bool


class IScheduler(ABC):
    @abstractmethod
    def worker_exists(self, name: str) -> bool: ...

    @abstractmethod
    def is_worker_running(self, name: str) -> bool: ...

    @abstractmethod
    def get_worker_info(self, name: str) -> WorkerInfo: ...

    @abstractmethod
    def list_workers(self) -> list[WorkerInfo]: ...

    @abstractmethod
    async def start_worker(self, name: str) -> None: ...

    @abstractmethod
    async def stop_worker(self, name: str) -> None: ...
