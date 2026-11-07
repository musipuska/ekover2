from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DatasetRead(BaseModel):
    """Информация о датасете для API."""

    id: str
    name: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetVersionRead(BaseModel):
    """Информация о версии исходного файла."""

    id: str
    dataset_id: str
    source_uri: str
    file_format: str
    checksum: str

    model_config = ConfigDict(from_attributes=True)


class DatasetDetail(DatasetRead):
    """Подробная информация о датасете."""

    versions: list[DatasetVersionRead] = []