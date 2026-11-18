import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.ml.data import load_curated
from backend.ml.features import FeatureConfig, build_features
from backend.ml.registry import ModelRegistry

PSI_WARNING = 0.1
PSI_ALERT = 0.25
EPSILON = 1e-4


def population_stability_index(reference_share: list[float], edges: list[float], values: np.ndarray) -> float:
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return float("nan")
    inner = np.asarray(edges[1:-1])
    bins = np.digitize(values, inner)
    actual = np.bincount(bins, minlength=len(reference_share)) / len(values)
    expected = np.clip(np.asarray(reference_share), EPSILON, None)
    actual = np.clip(actual, EPSILON, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def drift_status(value: float) -> str:
    if np.isnan(value):
        return "unknown"
    if value >= PSI_ALERT:
        return "alert"
    if value >= PSI_WARNING:
        return "warning"
    return "ok"


def monitor_batch(
    dataset_id: str,
    batch_id: str,
    model_name: str,
    model_version: str | None = None,
    allow_candidate: bool = False,
    registry: ModelRegistry | None = None,
    data_root: str | None = None,
    predictions: pd.DataFrame | None = None,
) -> dict:
    registry = registry or ModelRegistry()
    metadata = registry.resolve(model_name, model_version, allow_candidate)
    config = FeatureConfig.from_dict(metadata["feature_config"])

    frame, _ = load_curated(dataset_id, batch_id, data_root)
    features, _ = build_features(frame, config)

    drift = {}
    for name in metadata["features"]:
        info = metadata["feature_stats"][name]
        value = population_stability_index(
            info["hist_share"], info["hist_edges"], features[name].to_numpy(dtype="float64")
        )
        drift[name] = {"psi": None if np.isnan(value) else value, "status": drift_status(value)}

    report = {
        "dataset_id": dataset_id,
        "batch_id": batch_id,
        "model_name": model_name,
        "model_version": metadata["model_version"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_drift": drift,
        "drifted_features": [name for name, item in drift.items() if item["status"] in {"warning", "alert"}],
        "overall_status": "ok",
    }
    statuses = {item["status"] for item in drift.values()}
    if "alert" in statuses:
        report["overall_status"] = "alert"
    elif "warning" in statuses:
        report["overall_status"] = "warning"

    if predictions is not None and len(predictions):
        report["anomaly_rate"] = float(predictions["is_anomaly"].mean())
        report["score_quantiles"] = {
            str(q): float(predictions["anomaly_score"].quantile(q)) for q in (0.01, 0.05, 0.5, 0.95)
        }
        expected = metadata["params"]["contamination"]
        report["anomaly_rate_vs_contamination"] = float(report["anomaly_rate"] - expected)

    directory = (
        Path(data_root or settings.DATA_LAKE_PATH)
        / "monitoring"
        / "ml"
        / f"model_name={model_name}"
        / f"dataset_id={dataset_id}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"batch_id={batch_id}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report
