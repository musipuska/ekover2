import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from backend.app.infrastructure.database.models import (
    DataAsset,
    DataQualityResult,
    Dataset,
    ETLJob,
)
from backend.app.infrastructure.database.session import SessionLocal
from backend.etl.common.config import PipelineConfig, RuleSpec
from backend.etl.common.exceptions import QualityGateError, ValidationError
from backend.etl.common.run_context import RunContext
from backend.etl.jobs.full_pipeline import run_pipeline

CSV = (
    "Station ID,pH,Turbidity,Measured At\n"
    "s1,7.1,1.2,2026-01-01 10:00:00\n"
    "s1,7.1,1.2,2026-01-01 10:00:00\n"
    "s2,6.9,0.8,2026-01-01 11:00:00\n"
    "s3,15.2,0.5,2026-01-01 12:00:00\n"
    "s4,,0.4,2026-01-01 13:00:00\n"
)


def default_config(**overrides) -> PipelineConfig:
    config = PipelineConfig(
        rules=[
            RuleSpec(name="not_empty", rule="min_rows", threshold=1, severity="critical"),
            RuleSpec(
                name="ph_range", rule="between", column="ph",
                min=0, max=14, severity="warning", quarantine=True,
            ),
        ],
        timestamp_columns=["Measured At"],
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def layer_rows(ctx: RunContext, layer: str, sub: str = "") -> int:
    path = ctx.published_dir(layer) / sub if sub else ctx.published_dir(layer)
    return pq.read_table(str(path)).num_rows


def make_ctx(entry: dict) -> RunContext:
    return RunContext.from_ids(
        entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"]
    )


def test_full_pipeline_publishes_all_layers(spark, register_csv):
    entry = register_csv(CSV)
    result = run_pipeline(
        entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
        config=default_config(), spark=spark,
    )
    ctx = make_ctx(entry)

    assert result["status"] == "success"
    assert result["quality_status"] == "warning"
    assert layer_rows(ctx, "bronze") == 5
    assert layer_rows(ctx, "silver") == 4
    assert layer_rows(ctx, "quarantine") == 1
    assert layer_rows(ctx, "gold", "measurements") == 3

    gold_manifest = json.loads(ctx.manifest_path("gold").read_text(encoding="utf-8"))
    assert gold_manifest["status"] == "published"
    assert gold_manifest["quarantined_rows"] == 1

    profile = json.loads((ctx.layer_dir("gold") / "profile.json").read_text(encoding="utf-8"))
    assert profile["row_count"] == 3
    assert all(not column["name"].startswith("_") for column in profile["columns"])

    report = json.loads((ctx.layer_dir("gold") / "quality_report.json").read_text(encoding="utf-8"))
    assert report["quality_status"] == "warning"
    assert report["removed_duplicates"] == 1

    db = SessionLocal()
    try:
        job = db.query(ETLJob).filter(ETLJob.id == entry["job_id"]).one()
        assert job.status == "success"
        assert job.quality_status == "warning"
        assert job.finished_at is not None
        assert db.query(Dataset).filter(Dataset.id == entry["dataset_id"]).one().status == "success"
        layers = {a.layer for a in db.query(DataAsset).filter(DataAsset.dataset_id == entry["dataset_id"])}
        assert layers == {"bronze", "silver", "quarantine", "gold"}
        assert db.query(DataQualityResult).filter(
            DataQualityResult.dataset_id == entry["dataset_id"]
        ).count() == 2
    finally:
        db.close()


def test_bronze_has_technical_columns(spark, register_csv):
    entry = register_csv(CSV)
    run_pipeline(
        entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
        config=default_config(), spark=spark,
    )
    ctx = make_ctx(entry)
    table = pq.read_table(str(ctx.published_dir("bronze")))
    for name in (
        "_dataset_id", "_version_id", "_batch_id", "_ingested_at",
        "_source_file", "_source_row_number", "_record_hash",
    ):
        assert name in table.column_names
    numbers = sorted(table.column("_source_row_number").to_pylist())
    assert numbers == [1, 2, 3, 4, 5]
    hashes = table.column("_record_hash").to_pylist()
    assert len(set(hashes)) == 4


def test_rerun_is_idempotent_and_force_archives_previous(spark, register_csv):
    entry = register_csv(CSV)
    args = (entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"])
    run_pipeline(*args, config=default_config(), spark=spark)
    ctx = make_ctx(entry)
    first = json.loads(ctx.manifest_path("silver").read_text(encoding="utf-8"))

    run_pipeline(*args, config=default_config(), spark=spark)
    second = json.loads(ctx.manifest_path("silver").read_text(encoding="utf-8"))
    assert first["attempt_id"] == second["attempt_id"]
    assert len(list((ctx.layer_dir("silver") / "versions").glob("*/"))) == 1

    run_pipeline(*args, config=default_config(), spark=spark, force=True)
    third = json.loads(ctx.manifest_path("silver").read_text(encoding="utf-8"))
    assert third["attempt_id"] != first["attempt_id"]
    versions = [p for p in (ctx.layer_dir("silver") / "versions").iterdir() if p.is_dir()]
    assert len(versions) == 2
    assert third["previous_attempt_id"] == first["attempt_id"]
    assert layer_rows(ctx, "silver") == 4
    assert not (ctx.layer_dir("silver") / "_attempts").exists() or not any(
        (ctx.layer_dir("silver") / "_attempts").iterdir()
    )


def test_business_key_keeps_latest_record(spark, register_csv):
    entry = register_csv(
        "station_id,parameter,measured_at,value\n"
        "s1,ph,2026-01-01 10:00:00,7.0\n"
        "s1,ph,2026-01-01 10:00:00,7.4\n"
        "s1,ph,2026-01-01 11:00:00,7.1\n"
    )
    config = default_config(
        business_key=["station_id", "parameter", "measured_at"],
        timestamp_columns=["measured_at"],
        rules=[],
    )
    run_pipeline(
        entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
        config=config, spark=spark,
    )
    ctx = make_ctx(entry)
    table = pq.read_table(str(ctx.published_dir("gold") / "measurements")).to_pandas()
    assert len(table) == 2
    assert sorted(table["value"].tolist()) == [7.1, 7.4]


def test_critical_rule_blocks_gold(spark, register_csv):
    entry = register_csv(CSV)
    config = default_config(
        rules=[
            RuleSpec(name="station_not_null", rule="not_null", column="ph", severity="critical"),
        ]
    )
    with pytest.raises(QualityGateError):
        run_pipeline(
            entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
            config=config, spark=spark,
        )
    ctx = make_ctx(entry)
    gold_manifest = json.loads(ctx.manifest_path("gold").read_text(encoding="utf-8"))
    assert gold_manifest["status"] == "blocked"
    assert not ctx.published_dir("gold").exists()

    db = SessionLocal()
    try:
        job = db.query(ETLJob).filter(ETLJob.id == entry["job_id"]).one()
        assert job.status == "failed"
        assert job.quality_status == "failed"
        assert "QUALITY_GATE_FAILED" in job.error_message
        assert db.query(Dataset).filter(Dataset.id == entry["dataset_id"]).one().status == "failed"
    finally:
        db.close()


def test_missing_required_column_fails_before_spark(spark, register_csv):
    entry = register_csv(CSV)
    config = default_config(required_columns=["station_code"])
    with pytest.raises(Exception) as info:
        run_pipeline(
            entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
            config=config, spark=spark,
        )
    assert "SCHEMA_ERROR" in str(ETLJobError(entry["job_id"]))
    assert info.value.code == "SCHEMA_ERROR"


def ETLJobError(job_id: str) -> str:
    db = SessionLocal()
    try:
        return db.query(ETLJob).filter(ETLJob.id == job_id).one().error_message
    finally:
        db.close()


def test_empty_file_is_rejected(spark, register_csv):
    entry = register_csv(b"")
    with pytest.raises(ValidationError):
        run_pipeline(
            entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
            config=default_config(), spark=spark,
        )
    assert "VALIDATION_ERROR" in ETLJobError(entry["job_id"])


def test_checksum_mismatch_is_rejected(spark, register_csv):
    entry = register_csv(CSV)
    Path(entry["path"]).write_text(CSV + "s9,7.0,1.0,2026-01-02 10:00:00\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="Контрольная сумма"):
        run_pipeline(
            entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
            config=default_config(), spark=spark,
        )


def test_cp1251_file_is_read_correctly(spark, register_csv):
    entry = register_csv("станция,ph\nМосква,7.0\nКазань,7.2\n", encoding="cp1251")
    run_pipeline(
        entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
        config=default_config(timestamp_columns=[]), spark=spark,
    )
    ctx = make_ctx(entry)
    frame = pq.read_table(str(ctx.published_dir("gold") / "measurements")).to_pandas()
    assert sorted(frame["станция"].tolist()) == ["Казань", "Москва"]


def test_utf8_bom_header_is_normalized(spark, register_csv):
    entry = register_csv("﻿station,ph\ns1,7.0\ns2,7.2\n")
    run_pipeline(
        entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
        config=default_config(timestamp_columns=[]), spark=spark,
    )
    ctx = make_ctx(entry)
    frame = pq.read_table(str(ctx.published_dir("gold") / "measurements")).to_pandas()
    assert "station" in frame.columns


def test_duplicate_column_names_are_made_unique(spark, register_csv):
    entry = register_csv("ph,ph,temp\n7.0,7.5,20\n7.2,7.1,21\n")
    run_pipeline(
        entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
        config=default_config(timestamp_columns=[]), spark=spark,
    )
    ctx = make_ctx(entry)
    frame = pq.read_table(str(ctx.published_dir("gold") / "measurements")).to_pandas()
    business = [name for name in frame.columns if not name.startswith("_")]
    assert len(business) == len(set(business)) == 3


def test_critical_rule_on_missing_column_fails_gate(spark, register_csv):
    entry = register_csv(CSV)
    config = PipelineConfig(
        rules=[RuleSpec(name="need_x", rule="not_null", column="no_such_column", severity="critical")]
    )
    with pytest.raises(QualityGateError):
        run_pipeline(
            entry["dataset_id"], entry["version_id"], entry["job_id"], entry["batch_id"],
            config=config, spark=spark,
        )
    ctx = make_ctx(entry)
    report = json.loads((ctx.layer_dir("gold") / "quality_report.json").read_text(encoding="utf-8"))
    assert report["quality_status"] == "failed"
    assert report["critical_failures"] == 1
    assert report["quality_score"] == 0.0
