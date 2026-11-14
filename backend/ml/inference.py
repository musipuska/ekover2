import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.app.core.config import settings
from backend.ml.data import load_curated
from backend.ml.features import FeatureConfig, build_features
from backend.ml.registry import ModelRegistry

PREDICTION_NAMESPACE = uuid.UUID("6f1c2a9e-5a4b-4f0e-9a52-2c3d1f7b8e10")


def predictions_dir(
    model_name: str,
    model_version: str,
    dataset_id: str,
    batch_id: str,
    data_root: str | None = None,
) -> Path:
    return (
        Path(data_root or settings.DATA_LAKE_PATH)
        / "predictions"
        / f"model_name={model_name}"
        / f"model_version={model_version}"
        / f"dataset_id={dataset_id}"
        / f"batch_id={batch_id}"
    )


def _atomic_write(path: Path, writer) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    os.close(handle)
    try:
        writer(temp)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def batch_predict(
    dataset_id: str,
    batch_id: str,
    model_name: str,
    model_version: str | None = None,
    allow_candidate: bool = False,
    registry: ModelRegistry | None = None,
    data_root: str | None = None,
) -> dict:
    registry = registry or ModelRegistry()
    detector, metadata = registry.load(model_name, model_version, allow_candidate)
    version = metadata["model_version"]
    config = FeatureConfig.from_dict(metadata["feature_config"])

    frame, _ = load_curated(dataset_id, batch_id, data_root)
    features, _ = build_features(frame, config)
    scores, flags = detector.score(features)
    contexts = detector.explain(features)

    record_ids = (
        features["_record_hash"].astype(str)
        if "_record_hash" in features.columns
        else pd.Series(features.index.astype(str), index=features.index)
    )
    created = datetime.now(timezone.utc)
    station = config.station_column if config.station_column in features.columns else None

    result = pd.DataFrame(
        {
            "prediction_id": [
                str(uuid.uuid5(PREDICTION_NAMESPACE, f"{model_name}:{version}:{dataset_id}:{batch_id}:{rid}"))
                for rid in record_ids
            ],
            "dataset_id": dataset_id,
            "batch_id": batch_id,
            "record_id": record_ids.to_numpy(),
            "source_row_number": (
                features["_source_row_number"].to_numpy()
                if "_source_row_number" in features.columns else None
            ),
            "station_id": features[station].astype(str).to_numpy() if station else None,
            "model_name": model_name,
            "model_version": version,
            "anomaly_score": scores,
            "is_anomaly": flags,
            "feature_version": metadata.get("feature_version"),
            "context": [json.dumps(item, ensure_ascii=False) for item in contexts],
            "created_at": created.isoformat(),
        }
    )

    directory = predictions_dir(model_name, version, dataset_id, batch_id, data_root)
    _atomic_write(directory / "predictions.parquet", lambda target: result.to_parquet(target, index=False))

    summary = {
        "dataset_id": dataset_id,
        "batch_id": batch_id,
        "model_name": model_name,
        "model_version": version,
        "model_status": metadata["status"],
        "rows_scored": int(len(result)),
        "anomaly_count": int(result["is_anomaly"].sum()),
        "anomaly_rate": float(result["is_anomaly"].mean()),
        "status": "completed",
        "created_at": created.isoformat(),
        "path": str(directory / "predictions.parquet"),
    }
    _atomic_write(
        directory / "summary.json",
        lambda target: Path(target).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"),
    )
    return summary


def read_predictions(
    model_name: str | None = None,
    dataset_id: str | None = None,
    batch_id: str | None = None,
    only_anomalies: bool = False,
    data_root: str | None = None,
) -> pd.DataFrame:
    root = Path(data_root or settings.DATA_LAKE_PATH) / "predictions"
    frames = []
    for path in root.glob("model_name=*/model_version=*/dataset_id=*/batch_id=*/predictions.parquet"):
        parts = {item.split("=", 1)[0]: item.split("=", 1)[1] for item in path.parent.parts if "=" in item}
        if model_name and parts.get("model_name") != model_name:
            continue
        if dataset_id and parts.get("dataset_id") != dataset_id:
            continue
        if batch_id and parts.get("batch_id") != batch_id:
            continue
        frame = pd.read_parquet(path)
        if only_anomalies:
            frame = frame[frame["is_anomaly"]]
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values("anomaly_score").reset_index(drop=True)
