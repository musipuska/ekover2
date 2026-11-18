from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.analytics import ml_stats, pipeline_stats, quality_stats, repository
from backend.analytics.common import date_range, in_day_range, iso, safe_id, utc_bounds
from backend.app.infrastructure.database.models import Dataset


def _delta(current: int, previous: int | None) -> dict | None:
    if previous is None:
        return None
    return {
        "previous": previous,
        "change": current - previous,
        "change_pct": round((current - previous) / previous * 100, 1) if previous else None,
    }


def _previous_window(start, end):
    if not (start and end):
        return None, None
    days = (end - start).days + 1
    return start - timedelta(days=days), start - timedelta(days=1)


def _datasets_created(db: Session, dataset_id, start, end) -> list[Dataset]:
    low, high = utc_bounds(start, end)
    query = db.query(Dataset)
    if dataset_id:
        query = query.filter(Dataset.id == dataset_id)
    if low:
        query = query.filter(Dataset.created_at >= low)
    if high:
        query = query.filter(Dataset.created_at < high)
    return query.order_by(Dataset.created_at.desc()).all()


def _mart_scope(dataset_id, start, end) -> list[dict]:
    """Последняя опубликованная витрина каждого набора данных в выбранном периоде."""
    latest: dict[str, dict] = {}
    for item in reversed(repository.dataset_summaries(limit=500)["items"]):
        if dataset_id and item["dataset_id"] != dataset_id:
            continue
        if not in_day_range(item.get("published_at"), start, end):
            continue
        latest[item["dataset_id"]] = item
    return list(latest.values())


def summary(db: Session, dataset_id=None, date_from=None, date_to=None) -> dict:
    dataset_id = safe_id(dataset_id, "dataset_id")
    start, end = date_range(date_from, date_to)
    now = datetime.now(timezone.utc).isoformat()

    datasets = _datasets_created(db, dataset_id, start, end)
    pipeline = pipeline_stats.overview(db, dataset_id, date_from, date_to)
    performance = pipeline_stats.performance(db, dataset_id, date_from, date_to)
    quality = quality_stats.overview(db, dataset_id, date_from, date_to)
    ml = ml_stats.overview(dataset_id, date_from, date_to)

    scope = _mart_scope(dataset_id, start, end)
    stations, parameters = set(), set()
    for item in scope:
        stations.update(s["station_id"] for s in repository.station_metrics(item["dataset_id"], item["batch_id"])
                        if s.get("station_id") is not None)
        parameters.update(p["parameter"] for p in repository.parameter_metrics(item["dataset_id"], item["batch_id"]))
    measurements = sum(int(item["row_count"]) for item in scope) if scope else None

    # Динамика считается только при заданном периоде: сравниваем с равным по длине предыдущим.
    prev_start, prev_end = _previous_window(start, end)
    previous = {"datasets": None, "success": None, "failed": None}
    if prev_start:
        previous["datasets"] = len(_datasets_created(db, dataset_id, prev_start, prev_end))
        before = pipeline_stats.overview(db, dataset_id, prev_start.isoformat(), prev_end.isoformat())
        previous["success"], previous["failed"] = before["by_status"]["success"], before["by_status"]["failed"]

    success, failed = pipeline["by_status"]["success"], pipeline["by_status"]["failed"]
    q = quality["kpis"]
    kpis = [
        {"key": "datasets", "label": "Наборы данных", "value": len(datasets), "unit": "шт.",
         "description": "Загруженные наборы данных за выбранный период", "delta": _delta(len(datasets), previous["datasets"])},
        {"key": "measurements", "label": "Измерения", "value": measurements, "unit": "строк",
         "description": "Строки в Gold последних опубликованных витрин", "delta": None},
        {"key": "stations", "label": "Станции", "value": len(stations) if scope else None, "unit": "шт.",
         "description": "Уникальные идентификаторы станций в витринах (одинаковые ID разных наборов считаются один раз)",
         "delta": None},
        {"key": "parameters", "label": "Параметры", "value": len(parameters) if scope else None, "unit": "шт.",
         "description": "Уникальные числовые показатели в витринах", "delta": None},
        {"key": "jobs_success", "label": "Успешные обработки", "value": success, "unit": "шт.",
         "description": "ETL-задачи со статусом success", "delta": _delta(success, previous["success"])},
        {"key": "jobs_failed", "label": "Ошибки обработки", "value": failed, "unit": "шт.",
         "description": "ETL-задачи со статусом failed", "delta": _delta(failed, previous["failed"])},
        {"key": "quality_score", "label": "Средний Quality Score", "value": q["avg_quality_score"], "unit": "0–1",
         "description": "Среднее по последнему batch каждого набора данных", "delta": None},
        {"key": "anomalies", "label": "Аномалии", "value": ml["anomalies"] if ml["rows_scored"] else None, "unit": "шт.",
         "description": "Записи, помеченные детектором (по сохранённым предсказаниям)", "delta": None},
    ]

    per_day = Counter(iso(d.created_at)[:10] for d in datasets)
    anomalies_by_station, anomaly_model = [], None
    if ml["rows_scored"]:
        breakdown = ml_stats.anomalies_summary(dataset_id=dataset_id)
        anomalies_by_station = breakdown["by_station"][:10]
        anomaly_model = breakdown["model"]

    recent_jobs = pipeline_stats.list_jobs(db, dataset_id, date_from, date_to, limit=5)["items"]
    failed_recent = [job for job in pipeline_stats.list_jobs(db, dataset_id, limit=10)["items"] if job["status"] == "failed"]
    drift = ml_stats.drift(dataset_id=dataset_id)

    reasons, status = [], "healthy"
    if failed_recent:
        status = "degraded"
        reasons.append(f"Среди 10 последних задач ошибок: {len(failed_recent)}")
    if quality["status_distribution"].get("failed"):
        status = "degraded"
        reasons.append("Есть наборы данных, не прошедшие quality gate")
    if status == "healthy" and quality["status_distribution"].get("warning"):
        status = "warning"
        reasons.append("Есть наборы данных с предупреждениями quality gate")
    latest_drift = drift["latest"]["overall_status"] if drift["latest"] else None
    if latest_drift == "alert":
        status = "degraded"
        reasons.append("Дрейф признаков: alert")
    elif latest_drift == "warning":
        status = "warning" if status == "healthy" else status
        reasons.append("Дрейф признаков: warning")
    if not datasets and pipeline["total_jobs"] == 0 and not scope:
        status, reasons = "no_data", ["Нет данных за выбранный период"]

    return {
        "generated_at": now,
        "kpis": kpis,
        "dataset_activity": [{"date": day, "datasets": count} for day, count in sorted(per_day.items())],
        "processing_activity": performance["series"],
        "quality_distribution": quality["status_distribution"],
        "anomaly_overview": {"model": anomaly_model, "by_station": anomalies_by_station, "by_model": ml["models_used"]},
        "recent": {
            "datasets": [{"id": d.id, "name": d.name, "status": d.status, "created_at": iso(d.created_at)}
                         for d in datasets[:5]],
            "jobs": recent_jobs,
            "quality_reports": list(reversed(quality["trend"]))[:5],
            "errors": pipeline_stats.errors(db, dataset_id, date_from, date_to, limit=5)["items"],
        },
        "platform_status": {"status": status, "reasons": reasons},
    }
