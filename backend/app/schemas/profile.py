from pydantic import BaseModel


class ColumnProfile(BaseModel):
    """Статистика одного столбца."""

    name: str
    data_type: str
    null_count: int
    null_percent: float
    unique_count: int
    min_value: float | None = None
    max_value: float | None = None
    average_value: float | None = None


class DatasetProfile(BaseModel):
    """Профиль всего набора данных."""

    dataset_id: str
    batch_id: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile]