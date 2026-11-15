from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    """Информация о задаче обработки."""

    id: str
    dataset_version_id: str
    batch_id: str
    status: str
    error_message: str | None = None
    quality_status: str | None = None
    analytics_status: str | None = None
    ml_status: str | None = None
    pipeline_status: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)