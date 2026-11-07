
from pydantic import BaseModel


class DatasetQuality(BaseModel):
    """Отчёт о качестве обработанного набора данных."""

    dataset_id: str
    batch_id: str
    bronze_rows: int
    silver_rows: int
    removed_duplicates: int
    null_cells_after_cleaning: int
    quality_status: str
