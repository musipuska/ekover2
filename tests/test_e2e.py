import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.etl.common.config import PipelineConfig, RuleSpec
from backend.etl.jobs.full_pipeline import run_pipeline

client = TestClient(app)


def _csv() -> bytes:
    rng = np.random.default_rng(3)
    rows = ["station_id,measured_at,ph,temperature"]
    start = pd.Timestamp("2026-01-01")
    for i in range(120):
        rows.append(f"s{i % 2},{start + pd.Timedelta(hours=i // 2):%Y-%m-%d %H:%M:%S},{7 + rng.normal(0, .1):.3f},{15 + rng.normal(0, .3):.3f}")
    return ("\n".join(rows) + "\n").encode()


def test_upload_etl_marts_ml_and_api(spark, monkeypatch):
    from backend.app.api.v1 import uploads
    from backend.analytics.marts import build_marts
    from backend.etl.common.metadata import set_stage_status
    from backend.ml.features import FeatureConfig
    from backend.ml.registry import ModelRegistry
    from backend.ml.training import train_model

    monkeypatch.setattr(uploads, "start_etl_process", lambda **kwargs: None)
    ids = client.post(
        "/api/v1/datasets/uploads", files={"file": ("w.csv", _csv(), "text/csv")}
    ).json()

    config = PipelineConfig(
        timestamp_columns=["measured_at"],
        rules=[RuleSpec(name="ph", rule="between", column="ph", min=0, max=14, severity="critical")],
    )
    run_pipeline(ids["dataset_id"], ids["version_id"], ids["job_id"], ids["batch_id"], config=config, spark=spark)

    job = client.get(f"/api/v1/jobs/{ids['job_id']}").json()
    assert job["status"] == "success" and job["pipeline_status"] == "success"

    build_marts(ids["dataset_id"], ids["batch_id"])
    set_stage_status(ids["batch_id"], "analytics", "success")
    train_model(
        ids["dataset_id"], ids["batch_id"],
        config=FeatureConfig(timestamp_column="measured_at", station_column="station_id", rolling_window=3),
        registry=ModelRegistry(),
    )
    overview = client.get("/api/v1/analytics/overview").json()
    assert overview["data"]["datasets"] >= 1
    job = client.get(f"/api/v1/jobs/{ids['job_id']}").json()
    assert job["analytics_status"] == "success"
