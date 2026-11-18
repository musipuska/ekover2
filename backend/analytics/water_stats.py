import json

import numpy as np
import pandas as pd

from backend.analytics import repository
from backend.analytics.common import date_range, number, safe_id
from backend.analytics.marts import analytics_root
from backend.app.api.envelope import ApiError
from backend.etl.common.config import load_pipeline_config
from backend.ml.data import DataNotReadyError, load_curated

MAX_CORRELATION_PARAMETERS = 25
PERCENTILES = {"p01": 0.01, "p05": 0.05, "p25": 0.25, "median": 0.5, "p75": 0.75, "p95": 0.95, "p99": 0.99}


def thresholds() -> dict:
    """Границы из конфигурации quality gate. Это допустимые физические диапазоны, а не санитарные нормы."""
    config = load_pipeline_config()
    items = [
        {
            "parameter": rule.column,
            "min": rule.min,
            "max": rule.max,
            "severity": rule.severity,
            "rule": rule.name,
            "kind": "quality_gate_validity_range",
            "description": "Допустимый диапазон значений из конфигурации quality gate (etl/config/default.yaml). "
                           "Выход за границы помечает запись как недостоверную, это не санитарная норма.",
        }
        for rule in config.rules
        if rule.rule == "between" and rule.column
    ]
    return {"items": items, "regulatory_norms_configured": False}


def _threshold_for(parameter: str) -> dict | None:
    return next((item for item in thresholds()["items"] if item["parameter"] == parameter), None)


def _context(dataset_id: str, batch_id: str | None) -> tuple[str, dict]:
    dataset_id = safe_id(dataset_id, "dataset_id")
    batch = safe_id(batch_id, "batch_id") or repository.latest_batch(dataset_id)
    manifest = (
        analytics_root() / "manifests" / f"dataset_id={dataset_id}" / f"batch_id={batch}.json" if batch else None
    )
    if not manifest or not manifest.is_file():
        raise ApiError("ANALYTICS_NOT_FOUND", "Витрины для набора данных не построены", 404, {"dataset_id": dataset_id})
    return batch, json.loads(manifest.read_text(encoding="utf-8"))["mapping"]


def _gold(dataset_id: str, batch: str, columns: list[str]) -> pd.DataFrame:
    try:
        frame, _ = load_curated(dataset_id, batch, columns=list(dict.fromkeys(columns)))
    except DataNotReadyError as error:
        raise ApiError("DATA_NOT_READY", error.message, 409, error.details) from error
    return frame


def _apply_filters(frame: pd.DataFrame, mapping: dict, station_id, date_from, date_to) -> pd.DataFrame:
    start, end = date_range(date_from, date_to)
    if station_id:
        if not mapping.get("station_column"):
            raise ApiError("FILTER_NOT_SUPPORTED", "В наборе данных нет колонки станции", 422, {"filter": "station_id"})
        frame = frame[frame[mapping["station_column"]].astype(str) == station_id]
    if start or end:
        column = mapping.get("timestamp_column")
        if not column:
            raise ApiError("FILTER_NOT_SUPPORTED", "В наборе данных нет колонки времени", 422, {"filter": "date"})
        stamps = pd.to_datetime(frame[column], errors="coerce", utc=True)
        mask = stamps.notna()
        if start:
            mask &= stamps >= pd.Timestamp(start, tz="UTC")
        if end:
            mask &= stamps < pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
        frame = frame[mask]
    return frame


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("float64").replace([np.inf, -np.inf], np.nan)


def catalog(dataset_id: str, batch_id: str | None = None) -> dict:
    batch, mapping = _context(dataset_id, batch_id)
    summary = next(
        (item for item in repository.dataset_summaries(limit=500)["items"]
         if item["dataset_id"] == dataset_id and item["batch_id"] == batch),
        {},
    )
    stations = sorted({item["station_id"] for item in repository.station_metrics(dataset_id, batch)
                       if item.get("station_id") is not None})
    return {
        "dataset_id": dataset_id,
        "batch_id": batch,
        "parameters": mapping.get("parameter_columns") or [],
        "stations": stations,
        "has_station": bool(mapping.get("station_column")),
        "has_timestamp": bool(mapping.get("timestamp_column")),
        "row_count": summary.get("row_count"),
        "period_start": summary.get("period_start"),
        "period_end": summary.get("period_end"),
    }


def distribution(dataset_id, parameter, batch_id=None, station_id=None, date_from=None, date_to=None, bins=20) -> dict:
    batch, mapping = _context(dataset_id, batch_id)
    if parameter not in (mapping.get("parameter_columns") or []):
        raise ApiError("UNKNOWN_PARAMETER", "Параметр не найден в наборе данных", 422, {"parameter": parameter})
    columns = [parameter] + [mapping[k] for k in ("station_column", "timestamp_column") if mapping.get(k)]
    frame = _apply_filters(_gold(dataset_id, batch, columns), mapping, safe_id(station_id, "station_id"), date_from, date_to)
    values = _numeric(frame[parameter])
    valid = values.dropna().to_numpy()
    result = {
        "dataset_id": dataset_id, "batch_id": batch, "parameter": parameter, "station_id": station_id,
        "rows_in_scope": int(len(frame)), "n": int(len(valid)), "null_count": int(values.isna().sum()),
        "summary": None, "percentiles": None, "histogram": None, "boxplot": None, "threshold": None,
    }
    if len(valid) == 0:
        return result

    counts, edges = np.histogram(valid, bins=bins)
    q1, q3 = np.quantile(valid, [0.25, 0.75])
    iqr = q3 - q1
    inside = valid[(valid >= q1 - 1.5 * iqr) & (valid <= q3 + 1.5 * iqr)]
    outliers = np.sort(valid[(valid < q1 - 1.5 * iqr) | (valid > q3 + 1.5 * iqr)])
    result.update(
        summary={
            "mean": number(valid.mean()),
            "std": number(valid.std(ddof=1)) if len(valid) > 1 else None,
            "min": number(valid.min()),
            "max": number(valid.max()),
        },
        percentiles={label: number(np.quantile(valid, q)) for label, q in PERCENTILES.items()},
        histogram={"edges": [float(e) for e in edges], "counts": [int(c) for c in counts]},
        boxplot={
            "low": number(inside.min()), "q1": number(q1), "median": number(np.median(valid)),
            "q3": number(q3), "high": number(inside.max()),
            "outlier_count": int(len(outliers)),
            "outliers": [float(v) for v in outliers[:100]],
        },
    )
    limit = _threshold_for(parameter)
    if limit:
        result["threshold"] = {
            **limit,
            "below": int((valid < limit["min"]).sum()) if limit["min"] is not None else 0,
            "above": int((valid > limit["max"]).sum()) if limit["max"] is not None else 0,
        }
    return result


def correlation(dataset_id, batch_id=None, station_id=None, date_from=None, date_to=None,
                method="pearson", min_periods=10) -> dict:
    if method not in ("pearson", "spearman"):
        raise ApiError("INVALID_METHOD", "method: pearson или spearman", 422)
    batch, mapping = _context(dataset_id, batch_id)
    parameters = list(mapping.get("parameter_columns") or [])
    columns = parameters + [mapping[k] for k in ("station_column", "timestamp_column") if mapping.get(k)]
    frame = _apply_filters(_gold(dataset_id, batch, columns), mapping, safe_id(station_id, "station_id"), date_from, date_to)

    data = pd.DataFrame({name: _numeric(frame[name]) for name in parameters})
    data = data.loc[:, data.notna().sum() >= 2]
    truncated = data.shape[1] > MAX_CORRELATION_PARAMETERS
    if truncated:
        data = data[data.notna().sum().sort_values(ascending=False).index[:MAX_CORRELATION_PARAMETERS]]
    names = list(data.columns)

    matrix, counts = [], []
    for a in names:
        row, count_row = [], []
        for b in names:
            pair = data[[a]].dropna() if a == b else data[[a, b]].dropna()
            count_row.append(int(len(pair)))
            if len(pair) < min_periods or pair[a].nunique() < 2 or pair[b].nunique() < 2:
                row.append(None)
            elif a == b:
                row.append(1.0)
            else:
                row.append(number(pair[a].corr(pair[b], method=method)))
        matrix.append(row)
        counts.append(count_row)
    return {
        "dataset_id": dataset_id, "batch_id": batch, "method": method, "min_periods": min_periods,
        "parameters": names, "matrix": matrix, "pair_counts": counts, "truncated": truncated,
        "note": "Корреляция показывает статистическую связь и не доказывает причинно-следственную зависимость. "
                "Ячейки с малой выборкой или константным рядом не рассчитываются.",
    }


def measurements(dataset_id, parameter, batch_id=None, station_id=None, date_from=None, date_to=None,
                 limit=100, offset=0) -> dict:
    batch, mapping = _context(dataset_id, batch_id)
    if parameter not in (mapping.get("parameter_columns") or []):
        raise ApiError("UNKNOWN_PARAMETER", "Параметр не найден в наборе данных", 422, {"parameter": parameter})
    time_col, station_col = mapping.get("timestamp_column"), mapping.get("station_column")
    columns = [parameter, "_source_row_number", time_col, station_col]
    frame = _gold(dataset_id, batch, [c for c in columns if c])
    frame = _apply_filters(frame, mapping, safe_id(station_id, "station_id"), date_from, date_to)
    frame = frame.assign(_value=_numeric(frame[parameter])).dropna(subset=["_value"])
    if time_col:
        frame = frame.assign(_ts=pd.to_datetime(frame[time_col], errors="coerce", utc=True)).sort_values("_ts")
    limit_rule = _threshold_for(parameter)
    page = frame.iloc[offset: offset + limit]
    items = []
    for _, row in page.iterrows():
        value = float(row["_value"])
        outside = None
        if limit_rule:
            outside = bool(
                (limit_rule["min"] is not None and value < limit_rule["min"])
                or (limit_rule["max"] is not None and value > limit_rule["max"])
            )
        items.append({
            "row_number": int(row["_source_row_number"]) if "_source_row_number" in row and pd.notna(row["_source_row_number"]) else None,
            "measured_at": row["_ts"].isoformat() if time_col and pd.notna(row["_ts"]) else None,
            "station_id": str(row[station_col]) if station_col else None,
            "value": value,
            "outside_validity_range": outside,
        })
    return {"items": items, "total": int(len(frame)), "parameter": parameter, "dataset_id": dataset_id, "batch_id": batch}
