from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models import ETLJob


def create_job(
    db: Session,
    job: ETLJob
) -> ETLJob:
    """Создаёт задачу обработки."""

    db.add(job)
    db.flush()

    return job


def get_job(
    db: Session,
    job_id: str
) -> ETLJob | None:
    """Находит задачу по идентификатору."""

    return db.query(ETLJob).filter(
        ETLJob.id == job_id
    ).first()


def list_jobs(
    db: Session,
    dataset_version_id: str
) -> list[ETLJob]:
    """Возвращает задачи для конкретной версии датасета."""

    return (
        db.query(ETLJob)
        .filter(ETLJob.dataset_version_id == dataset_version_id)
        .order_by(ETLJob.created_at.desc())
        .all()
    )