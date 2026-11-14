import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.app.core.config import settings
from backend.ml.data import load_curated
from backend.ml.evaluation import supervised_report, temporal_split, unsupervised_report
from backend.ml.features import FeatureConfig, build_features
from backend.ml.model import AnomalyDetector
from backend.ml.registry import ModelRegistry

DEFAULT_MODEL_NAME = "water_anomaly_detector"


def runs_dir(data_root: str | None = None) -> Path:
    return Path(data_root or settings.DATA_LAKE_PATH) / "artifacts" / "ml_runs"


def save_run(record: dict, data_root: str | None = None) -> Path:
    directory = runs_dir(data_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record['run_id']}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=2, default=str)
    return path


def read_run(run_id: str, data_root: str | None = None) -> dict | None:
    path = runs_dir(data_root) / f"{run_id}.json"
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def train_model(
    dataset_id: str,
    batch_id: str,
    model_name: str = DEFAULT_MODEL_NAME,
    config: FeatureConfig | None = None,
    contamination: float = 0.02,
    label_column: str | None = None,
    train_fraction: float = 0.7,
    registry: ModelRegistry | None = None,
    data_root: str | None = None,
    run_id: str | None = None,
) -> dict:
    config = config or FeatureConfig()
    registry = registry or ModelRegistry()
    run_id = run_id or uuid.uuid4().hex
    record = {
        "run_id": run_id,
        "kind": "training",
        "status": "running",
        "dataset_id": dataset_id,
        "batch_id": batch_id,
        "model_name": model_name,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    save_run(record, data_root)

    try:
        frame, manifest = load_curated(dataset_id, batch_id, data_root)
        features, names = build_features(frame, config)

        if config.timestamp_column and config.timestamp_column in features.columns:
            train, test = temporal_split(features, config.timestamp_column, train_fraction)
            split = "temporal"
        else:
            train, test, split = features, None, "none"

        detector = AnomalyDetector(contamination=contamination).fit(train, names)
        train_scores, train_flags = detector.score(train)
        test_scores = test_flags = None
        if test is not None and len(test):
            test_scores, test_flags = detector.score(test)

        evaluation = unsupervised_report(train_scores, train_flags, test_scores, test_flags)
        evaluation["split"] = split
        if split == "none":
            evaluation["warning"] = "No timestamp column: evaluated on training data only"
        if label_column and label_column in frame.columns:
            target = test if test is not None and len(test) else train
            labels = frame.loc[target.index, label_column].to_numpy()
            scores = test_scores if test_scores is not None and len(test) else train_scores
            flags = test_flags if test_scores is not None and len(test) else train_flags
            evaluation["supervised"] = supervised_report(labels, scores, flags)

        def period(part):
            if part is None or not len(part) or not config.timestamp_column:
                return None
            stamps = part[config.timestamp_column]
            return [str(stamps.min()), str(stamps.max())]

        metadata = {
            "algorithm": "IsolationForest",
            "params": {
                "contamination": contamination,
                "n_estimators": detector.n_estimators,
                "random_state": detector.random_state,
            },
            "feature_config": config.to_dict(),
            "feature_version": config.version,
            "features": detector.feature_names,
            "feature_stats": detector.stats,
            "dataset_id": dataset_id,
            "batch_id": batch_id,
            "rows_total": int(len(features)),
            "rows_train": int(len(train)),
            "train_period": period(train),
            "test_period": period(test),
            "evaluation": evaluation,
            "quality_status": manifest.get("quality_status"),
            "code_version": os.getenv("GIT_SHA", "unknown"),
            "training_run_id": run_id,
        }
        registered = registry.register(model_name, detector, metadata)
        record.update(
            status="completed",
            model_version=registered["model_version"],
            evaluation=evaluation,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as error:
        record.update(
            status="failed",
            error=str(error),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        save_run(record, data_root)
        raise

    save_run(record, data_root)
    return record
