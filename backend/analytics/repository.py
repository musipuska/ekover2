import json
from pathlib import Path

import pandas as pd

from backend.analytics.marts import analytics_root


def _partition_value(path: Path, key: str) -> str | None:
    for part in path.parts:
        if part.startswith(f"{key}="):
            return part.split("=", 1)[1]
    return None


def _read_mart(mart: str, dataset_id: str | None = None, batch_id: str | None = None, data_root: str | None = None) -> pd.DataFrame:
    root = analytics_root(data_root) / mart
    frames = []
    if not root.is_dir():
        return pd.DataFrame()
    for path in root.glob("dataset_id=*/batch_id=*/data.parquet"):
        if dataset_id and _partition_value(path, "dataset_id") != dataset_id:
            continue
        if batch_id and _partition_value(path, "batch_id") != batch_id:
            continue
        frame = pd.read_parquet(path)
        frame["dataset_id"] = _partition_value(path, "dataset_id")
        frame["batch_id"] = _partition_value(path, "batch_id")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _clean(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records"))


def latest_batch(dataset_id: str, data_root: str | None = None) -> str | None:
    summary = _read_mart("dataset_summary", dataset_id, data_root=data_root)
    if summary.empty:
        return None
    return str(summary.sort_values("published_at").iloc[-1]["batch_id"])


def overview(data_root: str | None = None) -> dict:
    summary = _read_mart("dataset_summary", data_root=data_root)
    if summary.empty:
        return {"datasets": 0, "batches": 0, "rows": 0, "quality": {}}
    latest = summary.sort_values("published_at").groupby("dataset_id").tail(1)
    return {
        "datasets": int(latest["dataset_id"].nunique()),
        "batches": int(len(summary)),
        "rows": int(latest["row_count"].sum()),
        "quality": {str(k): int(v) for k, v in latest["quality_status"].value_counts().items()},
    }


def dataset_summaries(data_root: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    summary = _read_mart("dataset_summary", data_root=data_root)
    if summary.empty:
        return {"items": [], "total": 0}
    summary = summary.sort_values("published_at", ascending=False)
    return {"items": _clean(summary.iloc[offset: offset + limit]), "total": int(len(summary))}


def parameter_metrics(dataset_id: str, batch_id: str | None = None, data_root: str | None = None) -> list[dict]:
    batch = batch_id or latest_batch(dataset_id, data_root)
    if not batch:
        return []
    return _clean(_read_mart("parameter_metrics", dataset_id, batch, data_root))


def station_metrics(dataset_id: str, batch_id: str | None = None, parameter: str | None = None, data_root: str | None = None) -> list[dict]:
    batch = batch_id or latest_batch(dataset_id, data_root)
    if not batch:
        return []
    frame = _read_mart("station_metrics", dataset_id, batch, data_root)
    if parameter and not frame.empty:
        frame = frame[frame["parameter"] == parameter]
    return _clean(frame)


def trends(
    dataset_id: str,
    parameter: str,
    station_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    batch_id: str | None = None,
    limit: int = 1000,
    offset: int = 0,
    data_root: str | None = None,
) -> dict:
    batch = batch_id or latest_batch(dataset_id, data_root)
    if not batch:
        return {"items": [], "total": 0}
    frame = _read_mart("daily_metrics", dataset_id, batch, data_root)
    if frame.empty:
        return {"items": [], "total": 0}
    frame = frame[frame["parameter"] == parameter]
    if station_id:
        frame = frame[frame["station_id"] == station_id]
    if date_from:
        frame = frame[frame["date"] >= date_from]
    if date_to:
        frame = frame[frame["date"] <= date_to]
    frame = frame.sort_values("date")
    return {"items": _clean(frame.iloc[offset: offset + limit]), "total": int(len(frame))}
