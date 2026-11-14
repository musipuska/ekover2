import os
import shutil
import tempfile
from pathlib import Path

from backend.etl.common.exceptions import StorageError
from backend.etl.storage.base import StorageClient


class LocalStorageClient(StorageClient):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise StorageError("Путь вне корня хранилища", {"path": str(path)})
        return resolved

    def upload_file(self, local_path, destination: str) -> str:
        target = self._resolve(destination)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_path, target)
        except OSError as error:
            raise StorageError(str(error), {"path": destination}) from error
        return str(target)

    def download_file(self, source: str, local_path) -> Path:
        origin = self._resolve(source)
        destination = Path(local_path)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, destination)
        except OSError as error:
            raise StorageError(str(error), {"path": source}) from error
        return destination

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target == self.root:
            raise StorageError("Нельзя удалить корень хранилища")
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=True)
        except OSError as error:
            raise StorageError(str(error), {"path": path}) from error

    def list_objects(self, prefix: str) -> list[str]:
        base = self._resolve(prefix)
        if not base.exists():
            return []
        if base.is_file():
            return [str(base.relative_to(self.root))]
        return sorted(
            str(item.relative_to(self.root))
            for item in base.rglob("*")
            if item.is_file()
        )

    def read_bytes(self, path: str) -> bytes:
        try:
            return self._resolve(path).read_bytes()
        except OSError as error:
            raise StorageError(str(error), {"path": path}) from error

    def write_bytes(self, path: str, content: bytes) -> str:
        target = self._resolve(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
            with os.fdopen(handle, "wb") as file:
                file.write(content)
            os.replace(temp_name, target)
        except OSError as error:
            raise StorageError(str(error), {"path": path}) from error
        return str(target)
