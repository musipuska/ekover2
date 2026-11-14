import json
from pathlib import Path

from backend.app.core.config import settings
from backend.app.services import gold_reader


def get_dataset_quality(dataset_id: str, batch_id: str):
    path = gold_reader.batch_dir(dataset_id, batch_id) / "quality_report.json"
    if not path.is_file():
        path = (
            Path(settings.DATA_LAKE_PATH)
            / "gold"
            / "data_quality"
            / f"{dataset_id}_{batch_id}.json"
        )

    if not path.is_file():
        return None

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_dataset_batches(dataset_id: str) -> list[dict]:
    return gold_reader.list_batches(dataset_id)
