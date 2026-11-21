import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.analytics.common import (
    date_range,
    error_type,
    iso,
    safe_id,
    sanitize_error,
    utc_bounds,
)
from backend.app.api.envelope import ApiError
from backend.app.core.config import settings
from backend.app.infrastructure.database.models import (
    DataAsset,
    Dataset,
    DatasetVersion,
    ETLJob,
)

JOB_STATUSES = ("queued", "running", "success", "failed")
STAGES = ("validate_source", "bronze", "silver", "quality", "gold")
SORTABLE = {
    "created_at": ETLJob.created_at,
    "started_at": ETLJob.started_at,
    "finished_at": ETLJob.finished_at,
    "status": ETLJob.status,
    "dataset": Dataset.name,
}


def _filtered(db: Session, dataset_id, date_from, date_to, status=None):
    dataset_id = safe_id(dataset_id, "dataset_id")
    start, end = date_range(date_from, date_to)
    low, high = utc_bounds(start, end)
    if status is not None and status not in JOB_STATUSES:
        raise ApiError("INVALID_STATUS", f"Недопустимый статус. Допустимо: {', '.join(JOB_STATUSES)}", 422)
    query = (
        db.query(ETLJob, DatasetVersion, Dataset)
        .join(DatasetVersion, ETLJob.dataset_version_id == DatasetVersion.id)
        .join(Dataset, DatasetVersion.dataset_id == Dataset.id)
    )
    if dataset_id:
        query = query.filter(Dataset.id == dataset_id)
    if low:
        query = query.filter(ETLJob.created_at >= low)
    if high:
        query = query.filter(ETLJob.created_at < high)
    if status:
        query = query.filter(ETLJob.status == status)
    return query


def _duration(job: ETLJob) -> float | None:
    if job.started_at and job.finished_at:
        return round(max((job.finished_at - job.started_at).total_seconds(), 0.0), 3)
    return None


def _metrics(job: ETLJob) -> dict:
    if not job.metrics:
        return {}
    try:
        value = json.loads(job.metrics)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _row(job: ETLJob, version: DatasetVersion, dataset: Dataset) -> dict:
    return {
        "job_id": job.id,
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "batch_id": job.batch_id,
        "status": job.status,
        "stage": job.stage,
        "quality_status": job.quality_status,
        "analytics_status": job.analytics_status,
        "ml_status": job.ml_status,
        "pipeline_status": job.pipeline_status,
        "created_at": iso(job.created_at),
        "started_at": iso(job.started_at),
        "finished_at": iso(job.finished_at),
        "duration_seconds": _duration(job),
        "error_message": sanitize_error(job.error_message),
        "orchestrator_run_id": job.orchestrator_run_id,
    }


def overview(db: Session, dataset_id=None, date_from=None, date_to=None) -> dict:
    rows = _filtered(db, dataset_id, date_from, date_to).all()
    jobs = [job for job, _, _ in rows]
    counts = Counter(job.status or "unknown" for job in jobs)
    finished = counts.get("success", 0) + counts.get("failed", 0)
    durations = [d for d in (_duration(j) for j in jobs if j.status == "success") if d is not None]

    last = max(
        (item for item in rows),
        key=lambda item: item[0].finished_at or item[0].started_at or item[0].created_at,
        default=None,
    )
    stage_counts = {
        field: dict(Counter(getattr(job, field) for job in jobs if getattr(job, field)))
        for field in ("analytics_status", "ml_status", "pipeline_status", "quality_status")
    }
    return {
        "total_jobs": len(jobs),
        "by_status": {status: counts.get(status, 0) for status in JOB_STATUSES},
        "unknown_status_jobs": sum(v for k, v in counts.items() if k not in JOB_STATUSES),
        # Доля считается только от завершённых задач: queued/running в знаменатель не входят.
        "success_rate": round(counts.get("success", 0) / finished, 4) if finished else None,
        "avg_duration_seconds": round(sum(durations) / len(durations), 3) if durations else None,
        "max_duration_seconds": max(durations) if durations else None,
        "duration_sample_size": len(durations),
        "last_execution": _row(*last) if last else None,
        "stage_status_counts": stage_counts,
        "orchestration": {
            "mode": settings.ORCHESTRATOR,
            "jobs_with_orchestrator_run": sum(1 for job in jobs if job.orchestrator_run_id),
            # Статус DAG-run из Airflow backend не опрашивает: показываем только то, что хранит БД.
            "dag_status_polling": False,
        },
    }


def performance(db: Session, dataset_id=None, date_from=None, date_to=None) -> dict:
    rows = _filtered(db, dataset_id, date_from, date_to).all()
    daily: dict[str, dict] = defaultdict(
        lambda: {"jobs": 0, "success": 0, "failed": 0, "durations": [], "rows_silver": 0, "rows_gold": 0}
    )
    stage_values: dict[str, list[float]] = defaultdict(list)
    for job, _, _ in rows:
        day = iso(job.created_at)[:10]
        bucket = daily[day]
        bucket["jobs"] += 1
        if job.status == "success":
            bucket["success"] += 1
        elif job.status == "failed":
            bucket["failed"] += 1
        duration = _duration(job)
        if duration is not None and job.status == "success":
            bucket["durations"].append(duration)
        metrics = _metrics(job)
        bucket["rows_silver"] += int(metrics.get("rows_silver") or 0)
        bucket["rows_gold"] += int(metrics.get("rows_gold") or 0)
        for stage in STAGES:
            if isinstance(metrics.get(stage), (int, float)):
                stage_values[stage].append(float(metrics[stage]))

    series = [
        {
            "date": day,
            "jobs": item["jobs"],
            "success": item["success"],
            "failed": item["failed"],
            "avg_duration_seconds": round(sum(item["durations"]) / len(item["durations"]), 3)
            if item["durations"] else None,
            "rows_silver": item["rows_silver"],
            "rows_gold": item["rows_gold"],
        }
        for day, item in sorted(daily.items())
    ]
    return {
        "series": series,
        "stage_durations": [
            {
                "stage": stage,
                "avg_seconds": round(sum(values) / len(values), 3),
                "max_seconds": max(values),
                "samples": len(values),
            }
            for stage in STAGES
            if (values := stage_values.get(stage))
        ],
        "status_distribution": dict(Counter(job.status or "unknown" for job, _, _ in rows)),
    }


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_jobs(
    db: Session,
    dataset_id=None,
    date_from=None,
    date_to=None,
    status=None,
    search=None,
    sort_by="created_at",
    sort_dir="desc",
    limit=25,
    offset=0,
) -> dict:
    if sort_by not in SORTABLE:
        raise ApiError("INVALID_SORT", f"Сортировка доступна по: {', '.join(SORTABLE)}", 422)
    if sort_dir not in ("asc", "desc"):
        raise ApiError("INVALID_SORT", "sort_dir: asc или desc", 422)
    query = _filtered(db, dataset_id, date_from, date_to, status)
    if search:
        pattern = f"%{_escape_like(search.strip())}%"
        query = query.filter(
            ETLJob.id.ilike(pattern, escape="\\")
            | ETLJob.batch_id.ilike(pattern, escape="\\")
            | Dataset.name.ilike(pattern, escape="\\")
            | Dataset.id.ilike(pattern, escape="\\")
        )
    total = query.count()
    column = SORTABLE[sort_by]
    ordering = column.asc() if sort_dir == "asc" else column.desc()
    page = query.order_by(ordering, ETLJob.id).offset(offset).limit(limit).all()
    return {"items": [_row(*item) for item in page], "total": total}


def _stage_status(job: ETLJob, stage: str, metrics: dict) -> str:
    if job.status == "success":
        return "success"
    if job.stage == stage:
        return {"running": "running", "failed": "failed", "queued": "queued"}.get(job.status, "unknown")
    if stage in metrics:
        return "success"
    return "not_reached" if job.status in ("failed", "queued", "running") else "unknown"


def job_detail(db: Session, job_id: str) -> dict:
    safe_id(job_id, "job_id")
    found = (
        db.query(ETLJob, DatasetVersion, Dataset)
        .join(DatasetVersion, ETLJob.dataset_version_id == DatasetVersion.id)
        .join(Dataset, DatasetVersion.dataset_id == Dataset.id)
        .filter(ETLJob.id == job_id)
        .first()
    )
    if found is None:
        raise ApiError("JOB_NOT_FOUND", "Задача не найдена", 404, {"job_id": job_id})
    job, version, dataset = found
    metrics = _metrics(job)
    assets = (
        db.query(DataAsset)
        .filter(DataAsset.dataset_id == dataset.id, DataAsset.batch_id == job.batch_id)
        .order_by(DataAsset.created_at)
        .all()
    )
    asset_rows = {asset.layer: asset.row_count for asset in assets}
    rows_by_layer = {
        "bronze": metrics.get("rows_bronze", asset_rows.get("bronze")),
        "silver": metrics.get("rows_silver", asset_rows.get("silver")),
        "gold": metrics.get("rows_gold", asset_rows.get("gold")),
    }
    lifecycle = [
        {
            "stage": "upload",
            "label": "Загрузка",
            "status": "success",
            "duration_seconds": None,
            "rows": None,
            "at": iso(version.created_at),
        }
    ]
    for stage, label in (
        ("bronze", "Bronze"),
        ("silver", "Silver"),
        ("quality", "Quality gate"),
        ("gold", "Gold"),
    ):
        lifecycle.append(
            {
                "stage": stage,
                "label": label,
                "status": _stage_status(job, stage, metrics),
                "duration_seconds": metrics.get(stage) if isinstance(metrics.get(stage), (int, float)) else None,
                "rows": rows_by_layer.get(stage),
                "at": None,
            }
        )
    lifecycle.append(
        {"stage": "analytics", "label": "Analytics", "status": job.analytics_status or "not_run",
         "duration_seconds": None, "rows": None, "at": None}
    )
    lifecycle.append(
        {"stage": "ml", "label": "ML", "status": job.ml_status or "not_run",
         "duration_seconds": None, "rows": None, "at": None}
    )
    return {
        **_row(job, version, dataset),
        "source_filename": version.source_filename,
        "file_size_bytes": version.file_size_bytes,
        "metrics": metrics,
        "lifecycle": lifecycle,
        "assets": [
            {"layer": a.layer, "row_count": a.row_count, "format": a.format, "created_at": iso(a.created_at)}
            for a in assets
        ],
        # Моменты начала/конца отдельных этапов в БД не хранятся — только общая длительность и секунды по этапам.
        "stage_timestamps_available": False,
    }


def errors(db: Session, dataset_id=None, date_from=None, date_to=None, limit=20) -> dict:
    query = _filtered(db, dataset_id, date_from, date_to, "failed")
    total = query.count()
    rows = (
        query.order_by(func.coalesce(ETLJob.finished_at, ETLJob.created_at).desc()).limit(limit).all()
    )
    return {
        "items": [
            {
                "job_id": job.id,
                "dataset_id": dataset.id,
                "dataset_name": dataset.name,
                "batch_id": job.batch_id,
                "stage": job.stage,
                "error_type": error_type(job.error_message),
                "message": sanitize_error(job.error_message),
                "occurred_at": iso(job.finished_at or job.created_at),
            }
            for job, _, dataset in rows
        ],
        "total": total,
        "by_type": dict(Counter(error_type(job.error_message) for job, _, _ in query.all())),
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
