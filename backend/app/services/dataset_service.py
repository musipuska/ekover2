from sqlalchemy.orm import Session

from backend.app.core.exceptions import DatasetNotFoundError
from backend.app.repositories import dataset_repository


def get_all_datasets(db: Session):
    """Возвращает все зарегистрированные датасеты."""

    return dataset_repository.list_datasets(db)


def get_dataset_details(db: Session, dataset_id: str):
    """Возвращает датасет вместе со списком его версий."""

    dataset = dataset_repository.get_dataset(db, dataset_id)

    if dataset is None:
        raise DatasetNotFoundError("Датасет не найден.")

    dataset.versions = dataset_repository.get_versions(
        db,
        dataset_id
    )

    return dataset