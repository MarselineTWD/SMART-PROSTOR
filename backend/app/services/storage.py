"""S3-совместимое объектное хранилище (MinIO по умолчанию, любой S3 — по env).

boto3-клиент синхронный; для FastAPI async-путей заворачиваем вызовы в
`run_in_executor`. Presigned-ссылки строятся отдельным клиентом, который
использует `S3_PUBLIC_ENDPOINT_URL` — чтобы браузер получал ссылку на
доступный извне адрес MinIO (localhost:9000), а backend внутри compose
общался напрямую с `minio:9000`.
"""
from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from backend.app.core.config import settings


logger = logging.getLogger(__name__)


def _build_client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


class StorageService:
    """Тонкий фасад над boto3 S3."""

    def __init__(self) -> None:
        self._client = _build_client(settings.s3_endpoint_url)
        # Отдельный клиент только для генерации presigned URL — со внешним хостом.
        self._presign_client = _build_client(settings.s3_public_endpoint_url)

    # -- sync API ------------------------------------------------------------

    def ensure_bucket(self, bucket: str) -> None:
        try:
            self._client.head_bucket(Bucket=bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=bucket)
                logger.info("bucket created: %s", bucket)
            else:
                raise

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    def put_file(self, bucket: str, key: str, path: Path, content_type: str) -> None:
        with path.open("rb") as fh:
            self.put_object(bucket, key, fh.read(), content_type=content_type)

    def object_exists(self, bucket: str, key: str) -> bool:
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    def presigned_url(self, bucket: str, key: str, ttl: int | None = None) -> str:
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl or settings.s3_presign_ttl,
        )

    # -- async wrappers ------------------------------------------------------

    async def aput_file(
        self, bucket: str, key: str, path: Path, content_type: str
    ) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.put_file, bucket, key, path, content_type)

    async def aput_object(
        self, bucket: str, key: str, body: bytes, content_type: str
    ) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, self.put_object, bucket, key, body, content_type
        )

    async def apresigned_url(
        self, bucket: str, key: str, ttl: int | None = None
    ) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.presigned_url, bucket, key, ttl
        )


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    return StorageService()


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
