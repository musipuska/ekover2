from backend.app.infrastructure.database.session import get_db
from backend.app.infrastructure.storage.factory import get_storage


def get_storage_dependency():
    """Предоставляет выбранное файловое хранилище."""

    return get_storage()