from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Результат загрузки файла."""

    dataset_id: str
    version_id: str
    job_id: str
    batch_id: str
    filename: str
    status: str
    message: str