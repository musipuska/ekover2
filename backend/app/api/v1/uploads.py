
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    UploadFile,
    HTTPException,
)
from sqlalchemy.orm import Session

from backend.app.dependencies import get_storage_dependency
from backend.app.infrastructure.database.session import get_db
from backend.app.infrastructure.storage.base import StorageInterface
from backend.app.schemas.upload import UploadResponse
from backend.app.services.ingestion_service import upload_dataset
from backend.app.services.etl_runner import start_etl_process
from backend.app.core.exceptions import InvalidFileError


router = APIRouter(
    prefix="/datasets",
    tags=["Uploads"],
)


@router.post(
    "/uploads",
    response_model=UploadResponse,
    status_code=202,
)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: StorageInterface = Depends(get_storage_dependency),
):
    """Принимает CSV, сохраняет его и запускает ETL."""

    content = await file.read()

    try:
        result = upload_dataset(
            db=db,
            storage=storage,
            filename=file.filename or "dataset.csv",
            content=content,
        )

        # Запускаем ETL только после успешной регистрации задачи в БД.
        background_tasks.add_task(
            start_etl_process,
            dataset_id=result["dataset_id"],
            version_id=result["version_id"],
            job_id=result["job_id"],
            batch_id=result["batch_id"],
        )

        return result

    except InvalidFileError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
