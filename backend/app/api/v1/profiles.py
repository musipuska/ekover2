from fastapi import APIRouter, HTTPException

from backend.app.schemas.profile import DatasetProfile
from backend.app.services.profile_service import get_dataset_profile


router = APIRouter(
    prefix="/datasets",
    tags=["Profiles"]
)


@router.get(
    "/{dataset_id}/profile",
    response_model=DatasetProfile
)
def get_profile(dataset_id: str):
    """Возвращает профиль обработанного датасета."""

    profile = get_dataset_profile(dataset_id)

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Профиль пока не сформирован."
        )

    return profile