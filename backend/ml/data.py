from pathlib import Path

import pandas as pd

from backend.app.core.config import settings
from backend.etl.common.exceptions import QualityGateError
from backend.etl.common.publish import read_json
from backend.etl.common.versions import resolve_published


class DataNotReadyError(QualityGateError):
    code = "DATA_NOT_READY"


def gold_batch_dir(dataset_id: str, batch_id: str, data_root: str | None = None) -> Path:
    return (
        Path(data_root or settings.DATA_LAKE_PATH)
        / "gold"
        / f"dataset_id={dataset_id}"
        / f"batch_id={batch_id}"
    )


def load_curated(
    dataset_id: str,
    batch_id: str,
    data_root: str | None = None,
    allow_warning: bool = True,
) -> tuple[pd.DataFrame, dict]:
    directory = gold_batch_dir(dataset_id, batch_id, data_root)
    manifest = read_json(directory / "manifest.json")
    if not manifest or manifest.get("status") != "published":
        raise DataNotReadyError(
            "Gold для batch не опубликован",
            {"dataset_id": dataset_id, "batch_id": batch_id},
        )
    status = manifest.get("quality_status")
    if status == "failed" or (status == "warning" and not allow_warning):
        raise DataNotReadyError(
            "Batch не прошёл quality gate",
            {"quality_status": status},
        )
    frame = pd.read_parquet(resolve_published(directory) / "measurements")
    return frame, manifest
