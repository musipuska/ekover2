import io
from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.analytics import marts
from backend.analytics.common import date_range, error_type, safe_id, sanitize_error
from backend.analytics.quality_stats import ROW_RULES
from backend.app.api.envelope import ApiError
from backend.app.main import app
from backend.etl.common.config import PipelineConfig, RuleSpec
from backend.etl.jobs.full_pipeline import run_pipeline
from backend.etl.quality.rules import ROW_RULES as ETL_ROW_RULES
from backend.ml.features import FeatureConfig
from backend.ml.inference import batch_predict
from backend.ml.monitoring import monitor_batch
from backend.ml.training import train_model
from tests.test_ml_analytics import make_csv

client = TestClient(app)
API = "/api/v1/analytics"
MODEL = "dash_test_model"
FEATURES = FeatureConfig(timestamp_column="measured_at", station_column="station_id", rolling_window=5)


def get(path: str, **params):
    return client.get(f"{API}{path}", params={k: v for k, v in params.items() if v is not None})


def data(path: str, **params):
    response = get(path, **params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success" and {"request_id", "generated_at"} <= set(body["metadata"])
    return body["data"]


@pytest.fixture(scope="module")
def good(spark, register_csv):
    entry = register_csv(make_csv(), filename="dash_good.csv")
    config = PipelineConfig(
        timestamp_columns=["measured_at"],
        rules=[
            RuleSpec(name="rows", rule="min_rows", threshold=1, severity="critical"),
            RuleSpec(name="ph_range", rule="between", column="ph", min=0, max=14, severity="warning"),
        ],
    )
    run_pipeline(entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
                 config=config, spark=spark)
    marts.build_marts(entry["dataset_id"], entry["batch_id"])
    record = train_model(entry["dataset_id"], entry["batch_id"], model_name=MODEL, config=FEATURES, contamination=0.05)
    batch_predict(entry["dataset_id"], entry["batch_id"], MODEL, record["model_version"])
    monitor_batch(entry["dataset_id"], entry["batch_id"], MODEL, record["model_version"])
    return {**entry, "model_version": record["model_version"], "frame": pd.read_csv(io.StringIO(make_csv()))}


@pytest.fixture(scope="module")
def bad(spark, register_csv):
    entry = register_csv("ph\n7.0\n7.1\n", filename="dash_bad.csv")
    config = PipelineConfig(rules=[RuleSpec(name="x", rule="between", column="ph", min=100, max=200, severity="critical")])
    with pytest.raises(Exception):
        run_pipeline(entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
                     config=config, spark=spark)
    return entry


# --- helpers ----------------------------------------------------------------

def test_row_rules_stay_in_sync_with_etl():
    assert ROW_RULES == ETL_ROW_RULES


def test_sanitize_error_hides_paths_and_truncates():
    text = sanitize_error("STORAGE_ERROR: cannot read /home/vika/data/raw/x/file.csv now")
    assert "/home/vika" not in text and "<path>" in text
    assert len(sanitize_error("x" * 1000)) <= 300
    assert sanitize_error(None) is None


def test_error_type_parsing():
    assert error_type("QUALITY_GATE_FAILED: boom") == "QUALITY_GATE_FAILED"
    assert error_type("plain text") == "UNKNOWN" and error_type(None) == "UNKNOWN"


def test_validation_helpers():
    assert date_range("2026-01-01", "2026-01-31")[0].isoformat() == "2026-01-01"
    with pytest.raises(ApiError) as bad_date:
        date_range("31.01.2026", None)
    assert bad_date.value.status_code == 422
    with pytest.raises(ApiError):
        date_range("2026-02-01", "2026-01-01")
    for value in ("../x", "a/b", "a*", ".."):
        with pytest.raises(ApiError):
            safe_id(value, "dataset_id")
    assert safe_id("abc-123", "dataset_id") == "abc-123" and safe_id("", "x") is None


# --- overview -----------------------------------------------------------------

def test_summary_kpis_match_pipeline_data(good, bad):
    summary = data("/summary", dataset_id=good["dataset_id"])
    kpis = {item["key"]: item for item in summary["kpis"]}
    assert kpis["datasets"]["value"] == 1
    assert kpis["measurements"]["value"] == 240
    assert kpis["stations"]["value"] == 3 and kpis["parameters"]["value"] == 3
    assert kpis["jobs_success"]["value"] == 1 and kpis["jobs_failed"]["value"] == 0
    assert kpis["quality_score"]["value"] is not None
    assert 0 < kpis["anomalies"]["value"] < 240
    assert all(item["delta"] is None for item in summary["kpis"])  # период не задан → динамики нет
    drift_status = data("/ml/drift", dataset_id=good["dataset_id"])["latest"]["overall_status"]
    expected = {"ok": {"healthy"}, "warning": {"warning"}, "alert": {"degraded"}}[drift_status]
    assert summary["platform_status"]["status"] in expected  # единственный источник проблем здесь — отчёт о дрейфе
    assert summary["dataset_activity"][0]["datasets"] == 1
    assert summary["recent"]["jobs"][0]["job_id"] == good["job_id"]


def test_summary_failed_dataset_marks_platform_degraded(bad):
    summary = data("/summary", dataset_id=bad["dataset_id"])
    kpis = {item["key"]: item for item in summary["kpis"]}
    assert kpis["jobs_failed"]["value"] == 1 and kpis["jobs_success"]["value"] == 0
    assert kpis["measurements"]["value"] is None and kpis["anomalies"]["value"] is None  # N/A, не ноль
    assert summary["platform_status"]["status"] == "degraded"
    assert summary["recent"]["errors"][0]["job_id"] == bad["job_id"]


def test_summary_delta_only_with_period(good):
    today = datetime.now(timezone.utc).date().isoformat()
    summary = data("/summary", dataset_id=good["dataset_id"], date_from=today, date_to=today)
    delta = next(item for item in summary["kpis"] if item["key"] == "datasets")["delta"]
    assert delta == {"previous": 0, "change": 1, "change_pct": None}


def test_summary_period_without_data_is_no_data(good):
    summary = data("/summary", dataset_id=good["dataset_id"], date_from="2001-01-01", date_to="2001-01-31")
    assert summary["platform_status"]["status"] == "no_data"
    assert next(item for item in summary["kpis"] if item["key"] == "datasets")["value"] == 0


@pytest.mark.parametrize("path", ["/summary", "/pipeline/overview", "/quality/overview", "/pipeline/jobs"])
def test_filters_are_validated(path):
    assert get(path, date_from="not-a-date").json()["error"]["code"] == "INVALID_DATE"
    assert get(path, date_from="2026-02-01", date_to="2026-01-01").status_code == 422
    assert get(path, dataset_id="../etc").status_code == 422


# --- pipeline --------------------------------------------------------------------

def test_pipeline_overview_counts_and_rates(good, bad):
    ok_overview = data("/pipeline/overview", dataset_id=good["dataset_id"])
    assert ok_overview["by_status"]["success"] == 1 and ok_overview["success_rate"] == 1.0
    assert ok_overview["avg_duration_seconds"] is not None
    assert ok_overview["orchestration"]["dag_status_polling"] is False
    bad_overview = data("/pipeline/overview", dataset_id=bad["dataset_id"])
    assert bad_overview["by_status"]["failed"] == 1 and bad_overview["success_rate"] == 0.0
    assert bad_overview["avg_duration_seconds"] is None


def test_pipeline_jobs_filter_search_sort_paginate(good, bad):
    failed = data("/pipeline/jobs", status="failed", dataset_id=bad["dataset_id"])
    assert failed["total"] == 1 and failed["items"][0]["job_id"] == bad["job_id"]
    found = data("/pipeline/jobs", search="dash_good")
    assert good["job_id"] in {item["job_id"] for item in found["items"]}
    assert data("/pipeline/jobs", search="no-such-job-xyz")["total"] == 0
    assert data("/pipeline/jobs", search="%")["total"] == 0  # LIKE-метасимволы экранируются
    page = data("/pipeline/jobs", limit=1, offset=0, sort_by="status", sort_dir="asc")
    assert len(page["items"]) == 1 and page["total"] >= 2
    assert get("/pipeline/jobs", sort_by="password").json()["error"]["code"] == "INVALID_SORT"
    assert get("/pipeline/jobs", status="exploded").json()["error"]["code"] == "INVALID_STATUS"


def test_pipeline_job_detail_lifecycle(good, bad):
    detail = data(f"/pipeline/jobs/{good['job_id']}")
    stages = {item["stage"]: item for item in detail["lifecycle"]}
    assert list(stages) == ["upload", "bronze", "silver", "quality", "gold", "analytics", "ml"]
    assert all(stages[s]["status"] == "success" for s in ("bronze", "silver", "quality", "gold"))
    assert stages["gold"]["rows"] == 240 and stages["bronze"]["duration_seconds"] is not None
    assert {a["layer"] for a in detail["assets"]} >= {"bronze", "silver"}
    assert detail["stage_timestamps_available"] is False

    failed = data(f"/pipeline/jobs/{bad['job_id']}")
    assert failed["status"] == "failed" and failed["error_message"]
    assert not any(item["status"] == "success" for item in failed["lifecycle"] if item["stage"] == "gold")
    assert get("/pipeline/jobs/does-not-exist").json()["error"]["code"] == "JOB_NOT_FOUND"


def test_pipeline_errors_and_performance(good, bad):
    errors = data("/pipeline/errors", dataset_id=bad["dataset_id"])
    assert errors["total"] == 1 and errors["by_type"] == {"QUALITY_GATE_FAILED": 1}
    assert "/" not in errors["items"][0]["message"].split(":", 1)[0]
    performance = data("/pipeline/performance", dataset_id=good["dataset_id"])
    assert performance["series"][0]["success"] == 1 and performance["series"][0]["rows_gold"] == 240
    assert "bronze" in {item["stage"] for item in performance["stage_durations"]}


# --- data quality ------------------------------------------------------------------

def test_quality_overview_uses_real_reports(good):
    overview = data("/quality/overview", dataset_id=good["dataset_id"])
    assert overview["scope"] == "latest_batch_per_dataset"
    assert overview["status_distribution"] == {"passed": 1}
    layer = overview["layers"][0]
    assert (layer["bronze_rows"], layer["silver_rows"], layer["gold_rows"]) == (240, 240, 240)
    assert layer["removed_duplicates"] == 0 and layer["quarantined_rows"] == 0
    assert overview["kpis"]["rules_passed"] == 2 and overview["kpis"]["rules_failed"] == 0
    assert overview["ranking"][0]["quality_score"] == 1.0


def test_quality_rules_rate_only_for_row_rules(good):
    rules = data("/quality/rules", dataset_id=good["dataset_id"], sort_by="rule", sort_dir="asc")
    by_rule = {item["rule"]: item for item in rules["items"]}
    assert by_rule["ph_range"]["category"] == "row" and by_rule["ph_range"]["checked_rows"] == 240
    assert by_rule["ph_range"]["failure_rate"] == 0.0
    assert by_rule["rows"]["category"] == "dataset" and by_rule["rows"]["failure_rate"] is None
    assert data("/quality/rules", dataset_id=good["dataset_id"], status="failed")["total"] == 0
    assert data("/quality/rules", search="ph_")["total"] >= 1
    assert get("/quality/rules", status="nope").json()["error"]["code"] == "INVALID_STATUS"
    assert get("/quality/rules", severity="nope").status_code == 422


def test_quality_failed_rule_is_reported(bad):
    rules = data("/quality/rules", dataset_id=bad["dataset_id"])
    failed = [item for item in rules["items"] if item["status"] == "failed"]
    assert failed and failed[0]["severity"] == "critical" and failed[0]["failed_rows"] == 2
    assert failed[0]["failure_rate"] == 1.0
    assert rules["summary"]["by_status"]["failed"] >= 1


def test_quality_columns_and_null_history(good):
    report = data("/quality/columns", dataset_id=good["dataset_id"])
    names = {item["name"] for item in report["columns"]}
    assert {"ph", "temperature", "turbidity"} <= names
    assert report["problem_columns"] == []  # пропусков нет — ничего не выдумываем
    assert len(report["null_history"]) == 1 and report["null_history"][0]["null_percent"]["ph"] == 0.0
    assert get("/quality/columns", dataset_id="missing-dataset").json()["error"]["code"] == "PROFILE_NOT_FOUND"


# --- water quality --------------------------------------------------------------------

def test_water_catalog(good):
    catalog = data("/water/catalog", dataset_id=good["dataset_id"])
    assert catalog["parameters"] == ["ph", "temperature", "turbidity"]
    assert catalog["stations"] == ["s0", "s1", "s2"] and catalog["has_station"] and catalog["has_timestamp"]
    assert catalog["row_count"] == 240
    assert get("/water/catalog", dataset_id="missing").json()["error"]["code"] == "ANALYTICS_NOT_FOUND"


def test_distribution_matches_source_data(good):
    result = data("/water/distribution", dataset_id=good["dataset_id"], parameter="ph", bins=10)
    ph = good["frame"]["ph"]
    assert result["n"] == 240 and result["null_count"] == 0
    assert result["summary"]["mean"] == pytest.approx(ph.mean())
    assert result["summary"]["std"] == pytest.approx(ph.std())
    assert result["percentiles"]["median"] == pytest.approx(ph.median())
    assert sum(result["histogram"]["counts"]) == 240 and len(result["histogram"]["edges"]) == 11
    assert result["boxplot"]["outlier_count"] >= 1 and 9.5 in result["boxplot"]["outliers"]
    assert result["threshold"]["kind"] == "quality_gate_validity_range"
    assert (result["threshold"]["below"], result["threshold"]["above"]) == (0, 0)


def test_distribution_filters_change_data(good):
    frame = good["frame"]
    station = data("/water/distribution", dataset_id=good["dataset_id"], parameter="ph", station_id="s0")
    assert station["n"] == int((frame["station_id"] == "s0").sum()) == 80
    day = pd.to_datetime(frame["measured_at"]).dt.date.min().isoformat()
    one_day = data("/water/distribution", dataset_id=good["dataset_id"], parameter="ph", date_from=day, date_to=day)
    expected = int((pd.to_datetime(frame["measured_at"]).dt.date.astype(str) == day).sum())
    assert one_day["n"] == expected < 240
    empty = data("/water/distribution", dataset_id=good["dataset_id"], parameter="ph", station_id="nope")
    assert empty["n"] == 0 and empty["histogram"] is None and empty["summary"] is None
    assert get("/water/distribution", dataset_id=good["dataset_id"], parameter="nope").json()["error"]["code"] == "UNKNOWN_PARAMETER"
    assert get("/water/distribution", dataset_id=good["dataset_id"], parameter="ph", bins=1).status_code == 422


def test_correlation_matrix(good):
    result = data("/water/correlation", dataset_id=good["dataset_id"])
    size = len(result["parameters"])
    assert size == 3 and len(result["matrix"]) == size
    for i in range(size):
        assert result["matrix"][i][i] == pytest.approx(1.0)
        for j in range(size):
            assert result["matrix"][i][j] == pytest.approx(result["matrix"][j][i])
    expected = good["frame"]["ph"].corr(good["frame"]["temperature"])
    i, j = result["parameters"].index("ph"), result["parameters"].index("temperature")
    assert result["matrix"][i][j] == pytest.approx(expected)
    assert "причинно" in result["note"]
    assert data("/water/correlation", dataset_id=good["dataset_id"], method="spearman")["method"] == "spearman"
    assert get("/water/correlation", dataset_id=good["dataset_id"], method="kendall").status_code == 422
    sparse = data("/water/correlation", dataset_id=good["dataset_id"], station_id="s0", min_periods=500)
    assert all(cell is None for row in sparse["matrix"] for cell in row)  # выборка мала → не считаем


def test_thresholds_come_from_pipeline_config():
    result = data("/water/thresholds")
    assert result["regulatory_norms_configured"] is False
    ph = next(item for item in result["items"] if item["parameter"] == "ph")
    assert (ph["min"], ph["max"]) == (0, 14)


def test_measurements_drilldown(good):
    page = data("/water/measurements", dataset_id=good["dataset_id"], parameter="ph", limit=5)
    assert page["total"] == 240 and len(page["items"]) == 5
    stamps = [item["measured_at"] for item in page["items"]]
    assert stamps == sorted(stamps) and all(item["outside_validity_range"] is False for item in page["items"])
    assert get("/water/measurements", dataset_id=good["dataset_id"], parameter="ph", limit=501).status_code == 422


# --- ML ------------------------------------------------------------------------------------

def test_ml_overview(good):
    overview = data("/ml/overview", dataset_id=good["dataset_id"])
    assert overview["rows_scored"] == 240 and 0 < overview["anomalies"] < 240
    assert overview["normal"] == 240 - overview["anomalies"]
    assert overview["anomaly_rate"] == pytest.approx(overview["anomalies"] / 240)
    assert overview["models_used"][0]["model_name"] == MODEL
    assert overview["registry"]["production"] == [] or isinstance(overview["registry"]["production"], list)
    empty = data("/ml/overview", dataset_id="no-such-dataset")
    assert empty["rows_scored"] == 0 and empty["anomaly_rate"] is None and empty["last_detection_at"] is None


def test_anomalies_summary(good):
    summary = data("/ml/anomalies/summary", dataset_id=good["dataset_id"], batch_id=good["batch_id"])
    assert summary["model"]["model_name"] == MODEL
    assert {item["key"] for item in summary["by_station"]} == {"s0", "s1", "s2"}
    assert sum(item["total"] for item in summary["by_station"]) == 240
    hist = summary["score_histogram"]
    assert sum(hist["normal"]) + sum(hist["anomaly"]) == 240 and sum(hist["anomaly"]) == summary["anomalies"]
    assert summary["by_feature"] and "score_note" in summary
    nothing = data("/ml/anomalies/summary", dataset_id="no-such-dataset")
    assert nothing["rows_scored"] == 0 and nothing["score_histogram"] is None


def test_anomaly_series_and_markers(good):
    series = data("/ml/anomalies/series", dataset_id=good["dataset_id"], batch_id=good["batch_id"], parameter="ph")
    assert series["x_kind"] == "time" and len(series["normal"]) + len(series["anomalies"]) == 240
    assert series["downsampled"] is False and len(series["anomalies"]) > 0
    thin = data("/ml/anomalies/series", dataset_id=good["dataset_id"], batch_id=good["batch_id"],
                parameter="ph", max_points=100)
    assert thin["downsampled"] is True and len(thin["normal"]) <= 100
    assert len(thin["anomalies"]) == len(series["anomalies"])  # аномалии не прореживаются
    one = data("/ml/anomalies/series", dataset_id=good["dataset_id"], batch_id=good["batch_id"],
               parameter="ph", station_id="s1")
    assert len(one["normal"]) + len(one["anomalies"]) == 80
    assert {item["station"] for item in one["normal"]} == {"s1"}


def test_anomaly_series_errors(good):
    base = {"dataset_id": good["dataset_id"], "batch_id": good["batch_id"]}
    assert get("/ml/anomalies/series", parameter="nope", **base).json()["error"]["code"] == "UNKNOWN_PARAMETER"
    missing = get("/ml/anomalies/series", dataset_id="x", batch_id="y", parameter="ph")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "PREDICTIONS_NOT_FOUND"
    assert get("/ml/anomalies/series", dataset_id="../x", batch_id="y", parameter="ph").status_code == 422


def test_anomaly_scatter_and_records(good):
    base = {"dataset_id": good["dataset_id"], "batch_id": good["batch_id"]}
    scatter = data("/ml/anomalies/scatter", parameter_x="ph", parameter_y="turbidity", **base)
    assert len(scatter["normal"]) + len(scatter["anomalies"]) == 240
    records = data("/ml/anomalies/records", limit=5, **base)
    scores = [item["anomaly_score"] for item in records["items"]]
    assert scores == sorted(scores) and records["total"] > 0
    first = records["items"][0]
    assert {"ph", "temperature", "turbidity"} == set(first["values"]) and first["station_id"] in {"s0", "s1", "s2"}
    assert first["measured_at"] and first["model_version"] == good["model_version"]
    assert first["top_feature"]["feature"]
    # самая необычная запись — подсаженный выброс pH=9.5 / turbidity=9.0
    assert any(item["values"]["ph"] == pytest.approx(9.5) for item in records["items"])


def test_model_detail_does_not_invent_metrics(good):
    detail = data(f"/ml/models/{MODEL}")
    version = detail["versions"][0]
    assert version["model_version"] == good["model_version"] and version["algorithm"] == "IsolationForest"
    assert version["has_ground_truth"] is False and version["ground_truth_metrics"] is None
    assert version["evaluation"]["train_rows"] > 0 and "ph" in version["features"]
    assert detail["active_version"] is None  # модель в статусе candidate
    assert detail["detection_history"][0]["rows_scored"] == 240
    assert get("/ml/models/unknown_model").status_code == 404
    assert get("/ml/models/..%2F..").status_code in (400, 404)


def test_ml_runs_hide_tracebacks(good):
    runs = data("/ml/runs", kind="training")
    assert runs["total"] >= 1 and all("traceback" not in item for item in runs["items"])
    assert get("/ml/runs", kind="weird").status_code == 422


def test_drift_uses_real_report_and_thresholds(good):
    drift = data("/ml/drift", model_name=MODEL, dataset_id=good["dataset_id"])
    assert drift["available"] is True and drift["thresholds"]["warning"] == 0.1 and drift["thresholds"]["alert"] == 0.25
    report = drift["latest"]
    assert report["overall_status"] in {"ok", "warning", "alert"} and "ph" in report["feature_drift"]
    assert report["generated_at_source"] == "report"
    none = data("/ml/drift", dataset_id="no-such-dataset")
    assert none["available"] is False and none["reports"] == [] and none["latest"] is None
