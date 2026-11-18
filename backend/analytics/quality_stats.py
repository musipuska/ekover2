from collections import Counter

from sqlalchemy.orm import Session

from backend.analytics.common import date_range, in_day_range, iso, number, safe_id, utc_bounds
from backend.app.api.envelope import ApiError
from backend.app.infrastructure.database.models import DataAsset, DataQualityResult, Dataset
from backend.app.services import gold_reader
from backend.app.services.profile_service import get_dataset_profile
from backend.app.services.quality_service import get_dataset_quality

# Построчные правила выполняются над Silver (etl/jobs/quality_job.py), поэтому для них
# число проверенных записей = silver_rows. Совпадение с etl/quality/rules.py::ROW_RULES проверяет тест.
ROW_RULES = frozenset({"not_null", "between", "allowed_values", "regex", "valid_timestamp", "not_in_future"})
SEVERITIES = ("critical", "warning", "info")
RULE_STATUSES = ("passed", "failed", "skipped")
SORTABLE = {
    "created_at": DataQualityResult.created_at,
    "rule": DataQualityResult.rule_id,
    "severity": DataQualityResult.severity,
    "status": DataQualityResult.status,
    "failed_rows": DataQualityResult.failed_rows,
}


def _batch_entries(db: Session, dataset_id, start, end) -> list[dict]:
    query = db.query(Dataset)
    if dataset_id:
        query = query.filter(Dataset.id == dataset_id)
    entries = []
    for dataset in query.all():
        for batch in gold_reader.list_batches(dataset.id):
            if not in_day_range(batch["published_at"], start, end):
                continue
            report = get_dataset_quality(dataset.id, batch["batch_id"]) or {}
            bronze = report.get("bronze_rows")
            removed = report.get("removed_duplicates")
            entries.append(
                {
                    "dataset_id": dataset.id,
                    "dataset_name": dataset.name,
                    "batch_id": batch["batch_id"],
                    "published_at": batch["published_at"],
                    "publish_status": batch["status"],
                    "quality_status": batch["quality_status"] or report.get("quality_status"),
                    "quality_score": number(batch["quality_score"]),
                    "rule_coverage": number(report.get("rule_coverage")),
                    "critical_failures": report.get("critical_failures"),
                    "bronze_rows": bronze,
                    "silver_rows": report.get("silver_rows"),
                    "gold_rows": batch["row_count"],
                    "quarantined_rows": report.get("quarantined_rows"),
                    "removed_duplicates": removed,
                    "duplicate_rate": round(removed / bronze, 6) if bronze and removed is not None else None,
                    "null_cells": report.get("null_cells_after_cleaning"),
                    "checks_total": report.get("checks_total"),
                    "checks_passed": report.get("checks_passed"),
                    "checks_failed": report.get("checks_failed"),
                    "checks_skipped": report.get("checks_skipped"),
                }
            )
    entries.sort(key=lambda item: item["published_at"] or "")
    return entries


def _total(items: list[dict], key: str) -> int | None:
    values = [item[key] for item in items if isinstance(item.get(key), (int, float))]
    return int(sum(values)) if values else None


def _mean(items: list[dict], key: str) -> float | None:
    values = [item[key] for item in items if isinstance(item.get(key), (int, float))]
    return round(sum(values) / len(values), 4) if values else None


def overview(db: Session, dataset_id=None, date_from=None, date_to=None) -> dict:
    dataset_id = safe_id(dataset_id, "dataset_id")
    start, end = date_range(date_from, date_to)
    entries = _batch_entries(db, dataset_id, start, end)

    latest: dict[str, dict] = {}
    for entry in entries:  # entries отсортированы по времени публикации → последний перезаписывает
        latest[entry["dataset_id"]] = entry
    current = list(latest.values())

    ranking = sorted(
        current,
        key=lambda item: (item["quality_score"] is None, -(item["quality_score"] or 0.0)),
    )
    return {
        "scope": "latest_batch_per_dataset",
        "kpis": {
            "datasets_with_reports": len(current),
            "batches_total": len(entries),
            "avg_quality_score": _mean(current, "quality_score"),
            "avg_rule_coverage": _mean(current, "rule_coverage"),
            "gold_rows": _total(current, "gold_rows"),
            "silver_rows": _total(current, "silver_rows"),
            "null_cells": _total(current, "null_cells"),
            "duplicates_removed": _total(current, "removed_duplicates"),
            "quarantined_rows": _total(current, "quarantined_rows"),
            "rules_passed": _total(current, "checks_passed"),
            "rules_failed": _total(current, "checks_failed"),
            "rules_skipped": _total(current, "checks_skipped"),
        },
        "status_distribution": dict(Counter(item["quality_status"] or "unknown" for item in current)),
        "status_distribution_all_batches": dict(Counter(item["quality_status"] or "unknown" for item in entries)),
        "trend": entries,
        "ranking": ranking,
        # Слои сравниваются как независимые измерения каждого этапа, а не вычитанием:
        # Silver→Gold уменьшается на quarantine, Bronze→Silver — на дедупликацию.
        "layers": [
            {
                "dataset_id": item["dataset_id"],
                "dataset_name": item["dataset_name"],
                "batch_id": item["batch_id"],
                "bronze_rows": item["bronze_rows"],
                "silver_rows": item["silver_rows"],
                "gold_rows": item["gold_rows"],
                "removed_duplicates": item["removed_duplicates"],
                "quarantined_rows": item["quarantined_rows"],
                "null_cells": item["null_cells"],
            }
            for item in current
        ],
    }


def rules(
    db: Session,
    dataset_id=None,
    batch_id=None,
    status=None,
    severity=None,
    rule_type=None,
    search=None,
    sort_by="created_at",
    sort_dir="desc",
    limit=25,
    offset=0,
    date_from=None,
    date_to=None,
) -> dict:
    dataset_id, batch_id = safe_id(dataset_id, "dataset_id"), safe_id(batch_id, "batch_id")
    if status and status not in RULE_STATUSES:
        raise ApiError("INVALID_STATUS", f"status: {', '.join(RULE_STATUSES)}", 422)
    if severity and severity not in SEVERITIES:
        raise ApiError("INVALID_SEVERITY", f"severity: {', '.join(SEVERITIES)}", 422)
    if sort_by not in SORTABLE or sort_dir not in ("asc", "desc"):
        raise ApiError("INVALID_SORT", f"Сортировка доступна по: {', '.join(SORTABLE)}", 422)
    start, end = date_range(date_from, date_to)
    low, high = utc_bounds(start, end)

    query = db.query(DataQualityResult, Dataset).join(Dataset, DataQualityResult.dataset_id == Dataset.id)
    for column, value in (
        (Dataset.id, dataset_id),
        (DataQualityResult.batch_id, batch_id),
        (DataQualityResult.status, status),
        (DataQualityResult.severity, severity),
        (DataQualityResult.rule_type, rule_type),
    ):
        if value:
            query = query.filter(column == value)
    if low:
        query = query.filter(DataQualityResult.created_at >= low)
    if high:
        query = query.filter(DataQualityResult.created_at < high)
    if search:
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.filter(
            DataQualityResult.rule_id.ilike(pattern, escape="\\")
            | DataQualityResult.column_name.ilike(pattern, escape="\\")
        )

    total = query.count()
    summary = {
        "by_status": dict(Counter(row.status for row, _ in query.all())),
    }
    column = SORTABLE[sort_by]
    page = query.order_by(column.asc() if sort_dir == "asc" else column.desc(), DataQualityResult.id) \
        .offset(offset).limit(limit).all()

    pairs = {(row.dataset_id, row.batch_id) for row, _ in page}
    silver_rows = {}
    if pairs:
        for asset in db.query(DataAsset).filter(
            DataAsset.layer == "silver", DataAsset.dataset_id.in_({p[0] for p in pairs})
        ):
            silver_rows[(asset.dataset_id, asset.batch_id)] = asset.row_count

    items = []
    for row, dataset in page:
        checked = silver_rows.get((row.dataset_id, row.batch_id)) if row.rule_type in ROW_RULES else None
        failed = row.failed_rows
        items.append(
            {
                "rule": row.rule_id,
                "rule_type": row.rule_type,
                "category": "row" if row.rule_type in ROW_RULES else "dataset",
                "column": row.column_name,
                "severity": row.severity,
                "status": row.status,
                "failed_rows": failed,
                "checked_rows": checked,
                "failure_rate": round(failed / checked, 6) if checked and failed is not None else None,
                "observed_value": number(row.observed_value),
                "expected": row.expected_value,
                "dataset_id": row.dataset_id,
                "dataset_name": dataset.name,
                "batch_id": row.batch_id,
                "job_id": row.job_id,
                "created_at": iso(row.created_at),
            }
        )
    return {"items": items, "total": total, "summary": summary}


def columns(dataset_id: str, batch_id: str | None = None, max_batches: int = 30) -> dict:
    dataset_id, batch_id = safe_id(dataset_id, "dataset_id"), safe_id(batch_id, "batch_id")
    profile = get_dataset_profile(dataset_id, batch_id)
    if profile is None:
        raise ApiError("PROFILE_NOT_FOUND", "Профиль набора данных ещё не сформирован", 404, {"dataset_id": dataset_id})

    items = [
        {
            "name": item["name"],
            "data_type": item.get("data_type"),
            "null_count": item.get("null_count"),
            "null_percent": number(item.get("null_percent")),
            "unique_count": item.get("unique_count"),
            "is_system": str(item["name"]).startswith("_"),
        }
        for item in profile.get("columns", [])
    ]
    items.sort(key=lambda item: -(item["null_percent"] or 0.0))

    # Динамика пропусков: профиль хранится отдельно для каждого batch.
    history = []
    for batch in sorted(gold_reader.list_batches(dataset_id), key=lambda b: b["published_at"] or "")[-max_batches:]:
        past = get_dataset_profile(dataset_id, batch["batch_id"])
        if not past:
            continue
        history.append(
            {
                "batch_id": batch["batch_id"],
                "published_at": batch["published_at"],
                "null_percent": {
                    c["name"]: number(c.get("null_percent"))
                    for c in past.get("columns", [])
                    if not str(c["name"]).startswith("_")
                },
            }
        )
    return {
        "dataset_id": dataset_id,
        "batch_id": profile.get("batch_id"),
        "row_count": profile.get("row_count"),
        "columns": items,
        "problem_columns": [item for item in items if (item["null_percent"] or 0) > 0 and not item["is_system"]],
        "null_history": history,
    }
