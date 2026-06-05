"""Private object storage for progress photos.

Default backend talks to MinIO over the S3 API (boto3). A pure in-memory backend
is used in tests so they never touch the network. Choose via
`settings.DIARY_STORAGE_BACKEND` ("s3" | "memory").

Only object *keys* are stored in the DB; bytes are streamed back through the
owner-scoped API, so the bucket stays private (no public URLs).
"""
from __future__ import annotations

import functools

from django.conf import settings


class BaseStorage:
    def ensure_bucket(self) -> None:  # pragma: no cover - trivial
        pass

    def put(self, key: str, data: bytes, content_type: str = "image/jpeg") -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError


class MemoryStorage(BaseStorage):
    """In-process dict store for tests."""

    def __init__(self):
        self._objects: dict[str, bytes] = {}

    def put(self, key, data, content_type="image/jpeg"):
        self._objects[key] = bytes(data)

    def get(self, key):
        try:
            return self._objects[key]
        except KeyError as exc:
            raise FileNotFoundError(key) from exc

    def delete(self, key):
        self._objects.pop(key, None)


class S3Storage(BaseStorage):
    """MinIO/S3 backend via boto3. Lazily creates the client + bucket."""

    def __init__(self):
        self.bucket = settings.DIARY_S3_BUCKET
        self._endpoint = settings.DIARY_S3_ENDPOINT
        self._access_key = settings.DIARY_S3_ACCESS_KEY
        self._secret_key = settings.DIARY_S3_SECRET_KEY
        self._region = settings.DIARY_S3_REGION
        self.__client = None

    @property
    def _client(self):
        if self.__client is None:
            import boto3

            self.__client = boto3.client(
                "s3",
                endpoint_url=self._endpoint,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
            )
        return self.__client

    def ensure_bucket(self):
        from botocore.exceptions import ClientError

        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self.bucket)

    def put(self, key, data, content_type="image/jpeg"):
        self.ensure_bucket()
        self._client.put_object(
            Bucket=self.bucket, Key=key, Body=bytes(data), ContentType=content_type
        )

    def get(self, key):
        resp = self._client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def delete(self, key):
        self._client.delete_object(Bucket=self.bucket, Key=key)


@functools.lru_cache(maxsize=1)
def get_storage() -> BaseStorage:
    """Process-wide storage singleton chosen by settings.DIARY_STORAGE_BACKEND."""
    backend = getattr(settings, "DIARY_STORAGE_BACKEND", "s3")
    if backend == "memory":
        return MemoryStorage()
    return S3Storage()


def reset_storage_cache() -> None:
    """Drop the cached singleton (tests toggle the backend setting)."""
    get_storage.cache_clear()
