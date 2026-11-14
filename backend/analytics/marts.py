import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.etl.common.publish import utc_now
from backend.ml.data import load_curated

MARTS = ("dataset_summary", "parameter_metrics", "daily_metrics", "station_metrics")
QUANTILES = {"p05": 0.05, "p25": 0.25, "median": 0.5, "p75": 0.75, "p95": 0.95}


@dataclass
class AnalyticsMapping:
    timestamp_column: str | None = None
    station_column: str | None = None
    parameter_columns: list[str] | None = None


def analytics_root(data_root: str | None = None) -> Path:
    return Path(data_root or settings.DATA_LAKE_PATH) / "analytics"


def mart_dir(mart: str, dataset_id: str, batch_id: str, data_root: str | None = None) -> Path:
    return (
        analytics_root(data_root)
        / mart
        / f"dataset_id={dataset_id}"
        / f"batch_id={batch_id}"
    )


def detect_mapping(df: pd.DataFrame, mapping: AnalyticsMapping | None = None) -> AnalyticsMapping:
    mapping = mapping or AnalyticsMapping()
    timestamp = mapping.timestamp_column
    if timestamp is None:
        for name in ("measured_at", "timestamp", "datetime", "date"):
            if name in df.columns:
                timestamp = name
                break
        if timestamp is None:
            datetime_columns = [
                name for name in df.columns
                if pd.api.types.is_datetime64_any_dtype(df[name])
            ]
            timestamp = datetime_columns[0] if datetime_columns else None
    station = mapping.station_column
    if station is None:
        for name in ("station_id", "station", "station_code", "site_id"):
            if name in df.columns:
                station = name
                break
    parameters = mapping.parameter_columns
    if parameters is None:
        parameters = [
            name for name in df.columns
            if not name.startswith("_")
            and name not in {timestamp, station}
            and pd.api.types.is_numeric_dtype(df[name])
            and not pd.api.types.is_bool_dtype(df[name])
        ]
    return AnalyticsMapping(timestamp, station, parameters)


def dataset_summary(df: pd.DataFrame, mapping: AnalyticsMapping, manifest: dict) -> pd.DataFrame:
    period_start = period_end = None
    if mapping.timestamp_column:
        stamps = pd.to_datetime(df[mapping.timestamp_column], errors="coerce", utc=True).dropna()
        if len(stamps):
            period_start, period_end = stamps.min().isoformat(), stamps.max().isoformat()
    return pd.DataFrame(
        [
            {
                "dataset_id": manifest["dataset_id"],
                "batch_id": manifest["batch_id"],
                "row_count": int(len(df)),
                "parameter_count": len(mapping.parameter_columns or []),
                "station_count": int(df[mapping.station_column].nunique()) if mapping.station_column else None,
                "period_start": period_start,
                "period_end": period_end,
                "quality_status": manifest.get("quality_status"),
                "quality_score": manifest.get("quality_score"),
                "quarantined_rows": manifest.get("quarantined_rows", 0),
                "published_at": manifest.get("published_at"),
            }
        ]
    )


def parameter_metrics(df: pd.DataFrame, mapping: AnalyticsMapping) -> pd.DataFrame:
    rows = []
    for name in mapping.parameter_columns or []:
        series = df[name].astype("float64").replace([np.inf, -np.inf], np.nan)
        valid = series.dropna()
        row = {
            "parameter": name,
            "count": int(len(valid)),
            "null_count": int(series.isna().sum()),
            "mean": float(valid.mean()) if len(valid) else None,
            "std": float(valid.std()) if len(valid) > 1 else None,
            "min": float(valid.min()) if len(valid) else None,
            "max": float(valid.max()) if len(valid) else None,
        }
        for label, q in QUANTILES.items():
            row[label] = float(valid.quantile(q)) if len(valid) else None
        rows.append(row)
    return pd.DataFrame(rows)


def _long(df: pd.DataFrame, parameters: list[str], keys: dict[str, pd.Series]) -> pd.DataFrame:
    frame = df[parameters].astype("float64").replace([np.inf, -np.inf], np.nan)
    for name, values in keys.items():
        frame[name] = values
    melted = frame.melt(id_vars=list(keys), var_name="parameter", value_name="value")
    return melted.dropna(subset=["value"])


_AGGREGATES = dict(
    measurement_count="count",
    avg_value="mean",
    min_value="min",
    max_value="max",
    std_value="std",
    median_value="median",
)


def daily_metrics(df: pd.DataFrame, mapping: AnalyticsMapping) -> pd.DataFrame:
    if not mapping.timestamp_column or not mapping.parameter_columns:
        return pd.DataFrame()
    stamps = pd.to_datetime(df[mapping.timestamp_column], errors="coerce", utc=True)
    valid = df.loc[stamps.notna()]
    keys = {"date": stamps[stamps.notna()].dt.strftime("%Y-%m-%d")}
    if mapping.station_column:
        keys["station_id"] = valid[mapping.station_column].astype(str)
    melted = _long(valid, mapping.parameter_columns, keys)
    if melted.empty:
        return pd.DataFrame()
    result = melted.groupby(list(keys) + ["parameter"])["value"].agg(**_AGGREGATES).reset_index()
    if "station_id" not in result.columns:
        result["station_id"] = None
    columns = ["date", "station_id", "parameter", *_AGGREGATES]
    return result[columns].sort_values(["date", "parameter"]).reset_index(drop=True)


def station_metrics(df: pd.DataFrame, mapping: AnalyticsMapping) -> pd.DataFrame:
    if not mapping.station_column or not mapping.parameter_columns:
        return pd.DataFrame()
    keys = {"station_id": df[mapping.station_column].astype(str)}
    melted = _long(df, mapping.parameter_columns, keys)
    if melted.empty:
        return pd.DataFrame()
    result = melted.groupby(["station_id", "parameter"])["value"].agg(**_AGGREGATES).reset_index()
    return result.sort_values(["station_id", "parameter"]).reset_index(drop=True)


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    os.close(handle)
    try:
        frame.to_parquet(temp, index=False)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def build_marts(
    dataset_id: str,
    batch_id: str,
    mapping: AnalyticsMapping | None = None,
    data_root: str | None = None,
) -> dict:
    df, manifest = load_curated(dataset_id, batch_id, data_root)
    mapping = detect_mapping(df, mapping)

    builders = {
        "dataset_summary": lambda: dataset_summary(df, mapping, manifest),
        "parameter_metrics": lambda: parameter_metrics(df, mapping),
        "daily_metrics": lambda: daily_metrics(df, mapping),
        "station_metrics": lambda: station_metrics(df, mapping),
    }
    written = {}
    for name, build in builders.items():
        frame = build()
        if frame is None or frame.empty:
            continue
        path = mart_dir(name, dataset_id, batch_id, data_root) / "data.parquet"
        _write_frame(path, frame)
        written[name] = {"path": str(path), "rows": int(len(frame))}

    summary = {
        "dataset_id": dataset_id,
        "batch_id": batch_id,
        "built_at": utc_now(),
        "source_rows": int(len(df)),
        "mapping": {
            "timestamp_column": mapping.timestamp_column,
            "station_column": mapping.station_column,
            "parameter_columns": mapping.parameter_columns,
        },
        "marts": written,
    }
    target = analytics_root(data_root) / "manifests" / f"dataset_id={dataset_id}" / f"batch_id={batch_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def validate_marts(dataset_id: str, batch_id: str, data_root: str | None = None) -> dict:
    df, _ = load_curated(dataset_id, batch_id, data_root)
    summary_path = mart_dir("dataset_summary", dataset_id, batch_id, data_root) / "data.parquet"
    if not summary_path.is_file():
        raise ValueError("dataset_summary mart is missing")
    summary = pd.read_parquet(summary_path).iloc[0]
    if int(summary["row_count"]) != len(df):
        raise ValueError("dataset_summary.row_count does not match Gold row count")

    daily_path = mart_dir("daily_metrics", dataset_id, batch_id, data_root) / "data.parquet"
    if daily_path.is_file():
        daily = pd.read_parquet(daily_path)
        mapping = detect_mapping(df)
        expected = int(
            df[mapping.parameter_columns]
            .loc[pd.to_datetime(df[mapping.timestamp_column], errors="coerce", utc=True).notna()]
            .notna()
            .sum()
            .sum()
        )
        if int(daily["measurement_count"].sum()) != expected:
            raise ValueError("daily_metrics measurement_count does not match Gold values")
    return {"validated": True, "rows": int(len(df))}
