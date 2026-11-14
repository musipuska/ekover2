import json
from pathlib import Path

from backend.app.core.config import settings
from backend.app.services import gold_reader


def get_dataset_profile(dataset_id: str, batch_id: str | None = None):
    batch = batch_id or gold_reader.latest_published_batch(dataset_id)

    if batch:
        path = gold_reader.batch_dir(dataset_id, batch) / "profile.json"
        if path.is_file():
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)

    legacy = Path(settings.DATA_LAKE_PATH) / "gold" / "column_profile" / f"{dataset_id}.json"
    if legacy.is_file():
        with legacy.open("r", encoding="utf-8") as file:
            return json.load(file)

    return None
