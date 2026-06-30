from __future__ import annotations

import asyncio
import io
from datetime import timedelta

import minio

from src.core.logger import AppLogger
from src.interfaces.clients.storage.client import IStorageClient


class MinIOClient(IStorageClient):
    __slots__ = ("_client", "_logger")

    def __init__(
        self,
        *,
        logger: AppLogger,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
    ) -> None:
        self._logger = logger
        self._client = minio.Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    async def upload_file(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        def _upload() -> None:
            self._client.put_object(bucket, key, io.BytesIO(data), len(data), content_type=content_type)

        await asyncio.to_thread(_upload)

    async def download_file(self, bucket: str, key: str) -> bytes:
        def _download() -> bytes:
            response = self._client.get_object(bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(_download)

    async def delete_file(self, bucket: str, key: str) -> None:
        await asyncio.to_thread(self._client.remove_object, bucket, key)

    async def get_presigned_url(self, bucket: str, key: str, expires: timedelta) -> str:
        return await asyncio.to_thread(self._client.presigned_get_object, bucket, key, expires)

    async def create_bucket(self, bucket: str) -> None:
        def _create() -> None:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)

        await asyncio.to_thread(_create)

    async def bucket_exists(self, bucket: str) -> bool:
        return await asyncio.to_thread(self._client.bucket_exists, bucket)

    async def close(self) -> None:
        pass

    async def health_check(self) -> bool:
        try:
            async with asyncio.timeout(5):
                await asyncio.to_thread(self._client.list_buckets)
            return True
        except Exception as e:
            self._logger.error("MinIO health check failed", error=e)
            return False
