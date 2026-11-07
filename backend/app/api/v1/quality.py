
from fastapi import APIRouter, HTTPException

from backend.app.schemas.quality import DatasetQuality
from backend.app.services.quality_service import get_dataset_quality


router = APIRouter(
    prefix="/datasets",
    tags=["Quality"],
)


@router.get(
    "/{dataset_id}/quality/{batch_id}",
    response_model=DatasetQuality,
)
def get_quality(dataset_id: str, batch_id: str):
    """Возвращает отчёт качества обработанного набора данных."""

    report = get_dataset_quality(dataset_id, batch_id)

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="Отчёт качества пока не сформирован.",
        )

    return report
