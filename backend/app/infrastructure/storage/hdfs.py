from pathlib import Path

from backend.app.infrastructure.storage.base import StorageInterface
from backend.app.core.exceptions import StorageError


class HDFSStorage(StorageInterface):
    """Заготовка адаптера для Hadoop HDFS."""

    def save(self, source_path: Path, destination: str) -> str:
        """Сохраняет файл в HDFS."""

        raise StorageError(
            "HDFS пока не подключён. Используйте STORAGE_TYPE=local."
        )

    def exists(self, uri: str) -> bool:
        """Проверяет наличие объекта в HDFS."""

        raise StorageError(
            "HDFS пока не подключён. Используйте STORAGE_TYPE=local."
        )