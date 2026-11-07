import shutil
from pathlib import Path

from backend.app.infrastructure.storage.base import StorageInterface
from backend.app.core.exceptions import StorageError


class LocalStorage(StorageInterface):
    """Реализация хранилища на локальном диске."""

    def __init__(self, root_path: str) -> None:
        self.root = Path(root_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, source_path: Path, destination: str) -> str:
        """Копирует файл в Data Lake."""

        target = (self.root / destination).resolve()

        if self.root not in target.parents:
            raise StorageError("Недопустимый путь сохранения.")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)
            return str(target)
        except OSError as error:
            raise StorageError("Не удалось сохранить файл.") from error

    def exists(self, uri: str) -> bool:
        """Проверяет, существует ли файл в локальном хранилище."""

        path = Path(uri).resolve()
        return path.is_file() and (
            path == self.root or self.root in path.parents
        )