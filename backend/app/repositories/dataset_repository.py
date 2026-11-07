from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models import (
    Dataset,
    DatasetVersion
)


def create_dataset(
    db: Session,
    dataset: Dataset
) -> Dataset:
    """Добавляет новый датасет в базу данных."""

    db.add(dataset)
    db.flush()

    return dataset


def create_version(
    db: Session,
    version: DatasetVersion
) -> DatasetVersion:
    """Добавляет новую версию исходного файла."""

    db.add(version)
    db.flush()

    return version


def get_dataset(
    db: Session,
    dataset_id: str
) -> Dataset | None:
    """Находит датасет по идентификатору."""

    return db.query(Dataset).filter(
        Dataset.id == dataset_id
    ).first()


def list_datasets(db: Session) -> list[Dataset]:
    """Возвращает список всех датасетов."""

    return (
        db.query(Dataset)
        .order_by(Dataset.created_at.desc())
        .all()
    )


def get_versions(
    db: Session,
    dataset_id: str
) -> list[DatasetVersion]:
    """Возвращает версии указанного датасета."""

    return (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .all()
    )