from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.infrastructure.database.session import get_db
from backend.app.schemas.job import JobRead
from backend.app.services import job_service


router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Возвращает состояние задачи обработки."""

    job = job_service.get_job_status(db, job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Задача не найдена."
        )

    return job