from abc import ABC, abstractmethod
from pathlib import Path


class StorageInterface(ABC):
    """Общий интерфейс для систем хранения файлов."""

    @abstractmethod
    def save(self, source_path: Path, destination: str) -> str:
        """Сохраняет файл и возвращает адрес сохранённого объекта."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, uri: str) -> bool:
        """Проверяет существование файла."""
        raise NotImplementedError