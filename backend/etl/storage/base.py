from abc import ABC, abstractmethod
from pathlib import Path


class StorageClient(ABC):
    @abstractmethod
    def upload_file(self, local_path: str | Path, destination: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def download_file(self, source: str, local_path: str | Path) -> Path:
        raise NotImplementedError

    @abstractmethod
    def exists(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_objects(self, prefix: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, path: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def write_bytes(self, path: str, content: bytes) -> str:
        raise NotImplementedError
