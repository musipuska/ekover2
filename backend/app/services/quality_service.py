
import json

from pathlib import Path

from backend.app.core.config import settings


def get_dataset_quality(dataset_id: str, batch_id: str):
    """Загружает отчёт качества из слоя Gold."""

    quality_path = (
        Path(settings.DATA_LAKE_PATH)
        / "gold"
        / "data_quality"
        / f"{dataset_id}_{batch_id}.json"
    )

    if not quality_path.is_file():
        return None

    with quality_path.open("r", encoding="utf-8") as file:
        return json.load(file)
