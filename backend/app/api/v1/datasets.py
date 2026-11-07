from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.infrastructure.database.session import get_db
from backend.app.schemas.dataset import DatasetRead, DatasetDetail
from backend.app.services import dataset_service
from backend.app.core.exceptions import DatasetNotFoundError


router = APIRouter(
    prefix="/datasets",
    tags=["Datasets"]
)


@router.get("", response_model=list[DatasetRead])
def get_datasets(
    db: Session = Depends(get_db)
):
    """Возвращает список датасетов."""

    return dataset_service.get_all_datasets(db)


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db)
):
    """Возвращает информацию о конкретном датасете."""

    try:
        return dataset_service.get_dataset_details(
            db,
            dataset_id
        )

    except DatasetNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        ) from error