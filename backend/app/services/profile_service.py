import json

from pathlib import Path

from backend.app.core.config import settings


def get_dataset_profile(dataset_id: str):
    """Загружает профиль датасета из слоя Gold."""

    profile_path = (
        Path(settings.DATA_LAKE_PATH)
        / "gold"
        / "column_profile"
        / f"{dataset_id}.json"
    )

    if not profile_path.is_file():
        return None

    with profile_path.open("r", encoding="utf-8") as file:
        return json.load(file)