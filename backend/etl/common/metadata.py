import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.infrastructure.database.models import (
    DataAsset,
    DataQualityResult,
    Dataset,
    DatasetVersion,
    ETLJob,
)
from backend.app.infrastructure.database.session import SessionLocal
from backend.etl.common.exceptions import ValidationError


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_version_info(version_id: str) -> dict:
    db = SessionLocal()
    try:
        version = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
        if version is None:
            raise ValidationError(
                f"Версия набора данных {version_id} не найдена",
                {"version_id": version_id},
            )
        return {
            "version_id": version.id,
            "dataset_id": version.dataset_id,
            "source_uri": version.source_uri,
            "checksum": version.checksum,
            "schema_version": version.schema_version or "1.0",
        }
    finally:
        db.close()


def update_job(job_id: str, **fields) -> None:
    if "metrics" in fields and not isinstance(fields["metrics"], str):
        fields["metrics"] = json.dumps(fields["metrics"], ensure_ascii=False, default=str)
    db = SessionLocal()
    try:
        job = db.query(ETLJob).filter(ETLJob.id == job_id).first()
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        db.commit()
    finally:
        db.close()


def mark_job_started(job_id: str, run_key: str, orchestrator_run_id: str | None = None) -> None:
    update_job(
        job_id,
        status="running",
        error_message=None,
        started_at=_now(),
        finished_at=None,
        run_key=run_key,
        orchestrator_run_id=orchestrator_run_id,
    )


def set_job_stage(job_id: str, stage: str) -> None:
    update_job(job_id, stage=stage)


def mark_job_finished(
    job_id: str,
    status: str,
    error_message: str | None = None,
    quality_status: str | None = None,
    metrics: dict | None = None,
) -> None:
    fields = {
        "status": status,
        "error_message": error_message,
        "finished_at": _now(),
    }
    if quality_status is not None:
        fields["quality_status"] = quality_status
    if metrics is not None:
        fields["metrics"] = metrics
    update_job(job_id, **fields)


def set_dataset_status(dataset_id: str, status: str) -> None:
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if dataset is not None:
            dataset.status = status
            db.commit()
    finally:
        db.close()


def record_asset(
    dataset_id: str,
    batch_id: str,
    layer: str,
    storage_uri: str,
    row_count: int | None,
    schema_version: str | None,
    run_key: str | None,
    file_format: str = "parquet",
) -> None:
    db = SessionLocal()
    try:
        if db.query(Dataset).filter(Dataset.id == dataset_id).first() is None:
            return
        db.query(DataAsset).filter(
            DataAsset.dataset_id == dataset_id,
            DataAsset.batch_id == batch_id,
            DataAsset.layer == layer,
            DataAsset.storage_uri == storage_uri,
        ).delete()
        db.add(
            DataAsset(
                dataset_id=dataset_id,
                batch_id=batch_id,
                layer=layer,
                storage_uri=storage_uri,
                format=file_format,
                row_count=row_count,
                schema_version=schema_version,
                run_key=run_key,
            )
        )
        db.commit()
    finally:
        db.close()


def record_quality_results(
    dataset_id: str,
    batch_id: str,
    job_id: str | None,
    results: list[dict],
) -> None:
    db = SessionLocal()
    try:
        if db.query(Dataset).filter(Dataset.id == dataset_id).first() is None:
            return
        db.query(DataQualityResult).filter(
            DataQualityResult.dataset_id == dataset_id,
            DataQualityResult.batch_id == batch_id,
        ).delete()
        for item in results:
            observed = item.get("observed_value")
            db.add(
                DataQualityResult(
                    dataset_id=dataset_id,
                    batch_id=batch_id,
                    job_id=job_id,
                    rule_id=item["rule"],
                    rule_type=item.get("rule_type"),
                    column_name=item.get("column"),
                    status=item["status"],
                    severity=item["severity"],
                    failed_rows=item.get("failed_rows"),
                    observed_value=float(observed) if isinstance(observed, (int, float)) else None,
                    expected_value=str(item.get("expected")) if item.get("expected") is not None else None,
                )
            )
        db.commit()
    finally:
        db.close()


def previous_row_count(dataset_id: str, batch_id: str) -> int | None:
    db = SessionLocal()
    try:
        asset = (
            db.query(DataAsset)
            .filter(
                DataAsset.dataset_id == dataset_id,
                DataAsset.layer == "silver",
                DataAsset.batch_id != batch_id,
            )
            .order_by(DataAsset.created_at.desc())
            .first()
        )
        return int(asset.row_count) if asset and asset.row_count is not None else None
    finally:
        db.close()


def source_path_for(version_info: dict) -> Path:
    path = Path(version_info["source_uri"])
    if not path.is_file():
        raise ValidationError(
            f"Файл не найден: {path}",
            {"source_uri": version_info["source_uri"]},
        )
    return path
