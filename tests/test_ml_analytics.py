import json

import numpy as np
import pandas as pd
import pytest

from backend.analytics import marts, repository
from backend.etl.common.config import PipelineConfig, RuleSpec
from backend.etl.jobs.full_pipeline import run_pipeline
from backend.ml.data import DataNotReadyError
from backend.ml.evaluation import temporal_split
from backend.ml.features import FeatureConfig, build_features
from backend.ml.inference import batch_predict, read_predictions
from backend.ml.monitoring import monitor_batch
from backend.ml.registry import ModelRegistry, RegistryError
from backend.ml.training import train_model


def make_csv(rows: int = 240) -> str:
    rng = np.random.default_rng(7)
    lines = ["station_id,measured_at,ph,temperature,turbidity"]
    start = pd.Timestamp("2026-01-01")
    for index in range(rows):
        station = f"s{index % 3}"
        stamp = start + pd.Timedelta(hours=index // 3)
        ph = 7.0 + rng.normal(0, 0.1)
        temp = 15 + rng.normal(0, 0.5)
        turb = 1.0 + abs(rng.normal(0, 0.1))
        if index == rows - 2:
            ph, turb = 9.5, 9.0
        lines.append(f"{station},{stamp:%Y-%m-%d %H:%M:%S},{ph:.3f},{temp:.3f},{turb:.3f}")
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def batch(spark, register_csv):
    entry = register_csv(make_csv())
    config = PipelineConfig(
        timestamp_columns=["measured_at"],
        rules=[RuleSpec(name="rows", rule="min_rows", threshold=1, severity="critical")],
    )
    run_pipeline(
        entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
        config=config, spark=spark,
    )
    return entry


@pytest.fixture
def registry(tmp_path):
    return ModelRegistry(tmp_path / "models")


FEATURES = FeatureConfig(timestamp_column="measured_at", station_column="station_id", rolling_window=5)


def test_features_do_not_leak_future_values():
    frame = pd.DataFrame(
        {
            "station_id": ["a"] * 10,
            "measured_at": pd.date_range("2026-01-01", periods=10, freq="h"),
            "ph": np.arange(10, dtype=float),
        }
    )
    config = FeatureConfig(timestamp_column="measured_at", station_column="station_id", rolling_window=3, min_periods=2)
    base, _ = build_features(frame, config)

    changed = frame.copy()
    changed.loc[9, "ph"] = 1000.0
    after, _ = build_features(changed, config)

    pd.testing.assert_series_equal(base["ph_roll_mean"].iloc[:9], after["ph_roll_mean"].iloc[:9])
    assert base["ph_roll_mean"].iloc[9] == after["ph_roll_mean"].iloc[9]


def test_temporal_split_has_no_overlap():
    frame = pd.DataFrame({"measured_at": pd.date_range("2026-01-01", periods=100, freq="h")})
    train, test = temporal_split(frame, "measured_at", 0.7)
    assert train["measured_at"].max() < test["measured_at"].min()
    assert len(train) + len(test) == 100


def test_train_register_predict_flow(batch, registry):
    record = train_model(
        batch["dataset_id"], batch["batch_id"], config=FEATURES,
        contamination=0.02, registry=registry,
    )
    assert record["status"] == "completed"
    assert record["evaluation"]["split"] == "temporal"
    assert "test_anomaly_rate" in record["evaluation"]

    models = registry.list_models()
    assert models[0]["production_version"] is None
    with pytest.raises(RegistryError):
        batch_predict(batch["dataset_id"], batch["batch_id"], record["model_name"], registry=registry)

    summary = batch_predict(
        batch["dataset_id"], batch["batch_id"], record["model_name"],
        record["model_version"], registry=registry,
    )
    assert summary["rows_scored"] == 240
    assert summary["anomaly_count"] > 0

    predictions = read_predictions(record["model_name"], batch["dataset_id"], batch["batch_id"])
    assert len(predictions) == 240
    assert predictions["prediction_id"].is_unique
    context = json.loads(predictions.iloc[0]["context"])
    assert {"feature", "value", "expected_range", "deviation_sigma"} <= set(context["top_features"][0])

    again = batch_predict(
        batch["dataset_id"], batch["batch_id"], record["model_name"],
        record["model_version"], registry=registry,
    )
    assert again["rows_scored"] == 240
    assert len(read_predictions(record["model_name"], batch["dataset_id"], batch["batch_id"])) == 240

    worst = predictions.iloc[0]
    assert bool(worst["is_anomaly"])


def test_registry_requires_approval_for_production(batch, registry):
    record = train_model(batch["dataset_id"], batch["batch_id"], config=FEATURES, registry=registry)
    name, version = record["model_name"], record["model_version"]

    with pytest.raises(RegistryError):
        registry.set_status(name, version, "production", approved_by="me")
    registry.set_status(name, version, "staging")
    with pytest.raises(RegistryError):
        registry.set_status(name, version, "production")
    registry.set_status(name, version, "production", approved_by="reviewer")

    second = train_model(batch["dataset_id"], batch["batch_id"], config=FEATURES, registry=registry)
    registry.set_status(name, second["model_version"], "staging")
    registry.set_status(name, second["model_version"], "production", approved_by="reviewer")
    assert registry.get_metadata(name, version)["status"] == "archived"
    assert registry.resolve(name)["model_version"] == second["model_version"]


def test_registry_rejects_path_traversal(registry):
    with pytest.raises(RegistryError):
        registry.list_versions("../etc")


def test_monitoring_reports_drift(batch, registry):
    record = train_model(batch["dataset_id"], batch["batch_id"], config=FEATURES, registry=registry)
    report = monitor_batch(
        batch["dataset_id"], batch["batch_id"], record["model_name"],
        record["model_version"], registry=registry,
    )
    assert report["overall_status"] in {"ok", "warning", "alert"}
    assert "ph" in report["feature_drift"]


def test_training_blocked_for_failed_batch(spark, register_csv, registry):
    entry = register_csv("ph\n7.0\n7.1\n")
    config = PipelineConfig(rules=[RuleSpec(name="x", rule="between", column="ph", min=100, max=200, severity="critical")])
    with pytest.raises(Exception):
        run_pipeline(
            entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
            config=config, spark=spark,
        )
    with pytest.raises(DataNotReadyError):
        train_model(entry["dataset_id"], entry["batch_id"], registry=registry)


def test_build_and_validate_marts(batch):
    summary = marts.build_marts(batch["dataset_id"], batch["batch_id"])
    assert set(summary["marts"]) == {"dataset_summary", "parameter_metrics", "daily_metrics", "station_metrics"}
    assert marts.validate_marts(batch["dataset_id"], batch["batch_id"])["validated"]

    params = repository.parameter_metrics(batch["dataset_id"])
    assert {item["parameter"] for item in params} == {"ph", "temperature", "turbidity"}
    ph = next(item for item in params if item["parameter"] == "ph")
    assert ph["count"] == 240

    page = repository.trends(batch["dataset_id"], "ph", station_id="s0", limit=5)
    assert page["total"] == 4
    assert sum(item["measurement_count"] for item in page["items"]) == 80
    assert len(page["items"]) == 4

    daily = pd.read_parquet(
        marts.mart_dir("daily_metrics", batch["dataset_id"], batch["batch_id"]) / "data.parquet"
    )
    assert daily.groupby("parameter")["measurement_count"].sum().to_dict() == {"ph": 240, "temperature": 240, "turbidity": 240}

    assert repository.overview()["datasets"] >= 1
