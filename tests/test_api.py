
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.etl.common.config import PipelineConfig, RuleSpec
from backend.etl.jobs.full_pipeline import run_pipeline

client = TestClient(app)


def test_upload_then_read_results(spark, monkeypatch, tmp_path):
    from backend.app.api.v1 import uploads

    started = {}
    monkeypatch.setattr(uploads, "start_etl_process", lambda **kwargs: started.update(kwargs))

    response = client.post(
        "/api/v1/datasets/uploads",
        files={"file": ("water.csv", b"ph,turbidity\n7.1,1.0\n7.3,1.2\n15,0.9\n", "text/csv")},
    )
    assert response.status_code == 202
    ids = response.json()
    assert started["job_id"] == ids["job_id"]

    config = PipelineConfig(
        rules=[RuleSpec(name="ph", rule="between", column="ph", min=0, max=14, severity="warning", quarantine=True)]
    )
    run_pipeline(ids["dataset_id"], ids["version_id"], ids["job_id"], ids["batch_id"], config=config, spark=spark)

    job = client.get(f"/api/v1/jobs/{ids['job_id']}").json()
    assert job["status"] == "success"

    dataset = client.get(f"/api/v1/datasets/{ids['dataset_id']}").json()
    assert dataset["status"] == "success"
    assert dataset["versions"][0]["checksum"]

    profile = client.get(f"/api/v1/datasets/{ids['dataset_id']}/profile").json()
    assert profile["batch_id"] == ids["batch_id"] and profile["row_count"] == 2

    quality = client.get(f"/api/v1/datasets/{ids['dataset_id']}/quality/{ids['batch_id']}").json()
    assert quality["quality_status"] == "warning"
    assert quality["quarantined_rows"] == 1
    assert quality["results"][0]["rule"] == "ph"

    batches = client.get(f"/api/v1/datasets/{ids['dataset_id']}/batches").json()
    assert batches[0]["status"] == "published"


def test_upload_rejects_non_csv():
    response = client.post("/api/v1/datasets/uploads", files={"file": ("a.txt", b"x", "text/plain")})
    assert response.status_code == 400


def test_error_envelope_for_missing_model():
    response = client.get("/api/v1/ml/models/unknown_model")
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error" and body["error"]["code"] == "MODEL_NOT_FOUND"


def test_envelope_for_analytics_overview():
    body = client.get("/api/v1/analytics/overview").json()
    assert body["status"] == "success"
    assert {"request_id", "generated_at"} <= set(body["metadata"])


def test_training_run_returns_job_id(monkeypatch):
    from backend.app.api.v1 import ml

    monkeypatch.setattr(ml, "_run_training", lambda run_id, body: None)
    response = client.post("/api/v1/ml/training-runs", json={"dataset_id": "d", "batch_id": "b"})
    assert response.status_code == 202
    job_id = response.json()["data"]["job_id"]
    run = client.get(f"/api/v1/ml/runs/{job_id}").json()["data"]
    assert run["status"] == "queued"


def test_training_run_validates_contamination():
    response = client.post("/api/v1/ml/training-runs", json={"dataset_id": "d", "batch_id": "b", "contamination": 0.9})
    assert response.status_code == 422
