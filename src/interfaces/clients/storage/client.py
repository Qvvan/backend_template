from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta


class IStorageClient(ABC):
    @abstractmethod
    async def upload_file(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None: ...

    @abstractmethod
    async def download_file(self, bucket: str, key: str) -> bytes: ...

    @abstractmethod
    async def delete_file(self, bucket: str, key: str) -> None: ...

    @abstractmethod
    async def get_presigned_url(self, bucket: str, key: str, expires: timedelta) -> str: ...

    @abstractmethod
    async def create_bucket(self, bucket: str) -> None: ...

    @abstractmethod
    async def bucket_exists(self, bucket: str) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
