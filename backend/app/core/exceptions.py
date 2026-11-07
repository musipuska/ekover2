class EkoverError(Exception):
    """Базовая ошибка проекта."""


class StorageError(EkoverError):
    """Ошибка сохранения или чтения файла."""


class DatasetNotFoundError(EkoverError):
    """Запрашиваемый датасет не найден."""


class InvalidFileError(EkoverError):
    """Загружен файл неподдерживаемого формата."""