from backend.app.core.config import settings
from backend.app.infrastructure.storage.local import LocalStorage
from backend.app.infrastructure.storage.hdfs import HDFSStorage
from backend.app.infrastructure.storage.base import StorageInterface


def get_storage() -> StorageInterface:
    """Создаёт хранилище согласно настройкам проекта."""

    if settings.STORAGE_TYPE.lower() == "local":
        return LocalStorage(settings.DATA_LAKE_PATH)

    if settings.STORAGE_TYPE.lower() == "hdfs":
        return HDFSStorage()

    raise ValueError("Неизвестный тип хранилища.")