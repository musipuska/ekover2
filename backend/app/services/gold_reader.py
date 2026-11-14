import json
from pathlib import Path

from backend.app.core.config import settings


def gold_root() -> Path:
    return Path(settings.DATA_LAKE_PATH) / "gold"


def _read(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def batch_dir(dataset_id: str, batch_id: str) -> Path:
    return gold_root() / f"dataset_id={dataset_id}" / f"batch_id={batch_id}"


def list_batches(dataset_id: str) -> list[dict]:
    base = gold_root() / f"dataset_id={dataset_id}"
    if not base.is_dir():
        return []
    batches = []
    for path in base.iterdir():
        if not path.is_dir() or not path.name.startswith("batch_id="):
            continue
        manifest = _read(path / "manifest.json")
        report = _read(path / "quality_report.json")
        if manifest is None and report is None:
            continue
        batches.append(
            {
                "dataset_id": dataset_id,
                "batch_id": path.name.split("=", 1)[1],
                "status": (manifest or {}).get("status", "unknown"),
                "published_at": (manifest or {}).get("published_at"),
                "row_count": (manifest or {}).get("row_count"),
                "quality_status": (report or {}).get("quality_status"),
                "quality_score": (report or {}).get("quality_score"),
            }
        )
    batches.sort(key=lambda item: item["published_at"] or "", reverse=True)
    return batches


def latest_published_batch(dataset_id: str) -> str | None:
    for item in list_batches(dataset_id):
        if item["status"] == "published":
            return item["batch_id"]
    return None
