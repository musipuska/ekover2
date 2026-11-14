import os
from pathlib import Path

from backend.etl.common.exceptions import InfrastructureError, StorageError
from backend.etl.storage.base import StorageClient


class S3StorageClient(StorageClient):
    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
        client=None,
    ) -> None:
        self.bucket = bucket
        if client is not None:
            self.client = client
            return
        try:
            import boto3
        except ImportError as error:
            raise InfrastructureError(
                "Для S3StorageClient требуется пакет boto3"
            ) from error
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=access_key or os.getenv("S3_ACCESS_KEY"),
            aws_secret_access_key=secret_key or os.getenv("S3_SECRET_KEY"),
            region_name=region or os.getenv("S3_REGION"),
        )

    @staticmethod
    def _key(path: str) -> str:
        return path.lstrip("/")

    def upload_file(self, local_path, destination: str) -> str:
        key = self._key(destination)
        try:
            self.client.upload_file(str(local_path), self.bucket, key)
        except Exception as error:
            raise StorageError(str(error), {"path": destination}) from error
        return f"s3://{self.bucket}/{key}"

    def download_file(self, source: str, local_path) -> Path:
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(self.bucket, self._key(source), str(destination))
        except Exception as error:
            raise StorageError(str(error), {"path": source}) from error
        return destination

    def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise StorageError(str(error), {"path": path}) from error

    def delete(self, path: str) -> None:
        key = self._key(path)
        try:
            for item in self.list_objects(key):
                self.client.delete_object(Bucket=self.bucket, Key=item)
        except StorageError:
            raise
        except Exception as error:
            raise StorageError(str(error), {"path": path}) from error

    def list_objects(self, prefix: str) -> list[str]:
        keys: list[str] = []
        token = None
        try:
            while True:
                params = {"Bucket": self.bucket, "Prefix": self._key(prefix)}
                if token:
                    params["ContinuationToken"] = token
                response = self.client.list_objects_v2(**params)
                keys.extend(item["Key"] for item in response.get("Contents", []))
                if not response.get("IsTruncated"):
                    return sorted(keys)
                token = response.get("NextContinuationToken")
        except Exception as error:
            raise StorageError(str(error), {"path": prefix}) from error

    def read_bytes(self, path: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(path))
            return response["Body"].read()
        except Exception as error:
            raise StorageError(str(error), {"path": path}) from error

    def write_bytes(self, path: str, content: bytes) -> str:
        key = self._key(path)
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        except Exception as error:
            raise StorageError(str(error), {"path": path}) from error
        return f"s3://{self.bucket}/{key}"
