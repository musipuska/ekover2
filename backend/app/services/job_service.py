from sqlalchemy.orm import Session

from backend.app.repositories import job_repository


def get_job_status(db: Session, job_id: str):
    """Возвращает информацию о задаче обработки."""

    return job_repository.get_job(db, job_id)