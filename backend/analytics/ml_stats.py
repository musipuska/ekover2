import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from backend.analytics.common import date_range, in_day_range, number, safe_id, sanitize_error
from backend.analytics.marts import analytics_root, detect_mapping
from backend.app.api.envelope import ApiError
from backend.app.core.config import settings
from backend.ml.data import DataNotReadyError, load_curated
from backend.ml.inference import read_predictions
from backend.ml.monitoring import PSI_ALERT, PSI_WARNING
from backend.ml.registry import ModelRegistry, RegistryError
from backend.ml.training import runs_dir

SCORE_NOTE = (
    "anomaly_score — decision_function IsolationForest: чем ниже, тем аномальнее. "
    "Шкала зависит от модели и версии, поэтому разные модели не сравниваются между собой."
)
_DERIVED_SUFFIX = re.compile(r"_(dev|roll_mean|roll_std)$")
_PRED_COLUMNS = ["model_name", "model_version", "dataset_id", "batch_id", "station_id",
                 "anomaly_score", "is_anomaly", "created_at"]


def _lake() -> Path:
    return Path(settings.DATA_LAKE_PATH)


def _predictions(dataset_id=None, batch_id=None, model_name=None, model_version=None,
                 columns=None, only_anomalies=False, start=None, end=None) -> pd.DataFrame:
    frame = read_predictions(
        model_name=model_name, dataset_id=dataset_id, batch_id=batch_id,
        only_anomalies=only_anomalies, columns=columns, model_version=model_version,
    )
    if frame.empty or not (start or end) or "created_at" not in frame.columns:
        return frame
    keep = frame["created_at"].map(lambda value: in_day_range(str(value), start, end))
    return frame[keep].reset_index(drop=True)


def _read_runs() -> list[dict]:
    directory = runs_dir()
    runs = []
    if directory.is_dir():
        for path in directory.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            record.pop("traceback", None)  # stack trace — внутренняя информация, наружу не отдаём
            if record.get("error"):
                record["error"] = sanitize_error(str(record["error"]))
            runs.append(record)
    runs.sort(key=lambda r: r.get("finished_at") or r.get("started_at") or "", reverse=True)
    return runs


def runs(kind: str | None = None, status: str | None = None, limit: int = 20) -> dict:
    if kind and kind not in ("training", "inference"):
        raise ApiError("INVALID_KIND", "kind: training или inference", 422)
    items = [r for r in _read_runs() if (not kind or r.get("kind") == kind) and (not status or r.get("status") == status)]
    return {"items": items[:limit], "total": len(items)}


def overview(dataset_id=None, date_from=None, date_to=None) -> dict:
    dataset_id = safe_id(dataset_id, "dataset_id")
    start, end = date_range(date_from, date_to)
    registry = ModelRegistry().list_models()
    frame = _predictions(dataset_id=dataset_id, columns=_PRED_COLUMNS, start=start, end=end)
    inference_runs = [r for r in _read_runs() if r.get("kind") == "inference"]

    total = int(len(frame))
    anomalies = int(frame["is_anomaly"].sum()) if total else 0
    models_used = []
    if total:
        grouped = frame.groupby(["model_name", "model_version"])
        for (name, version), part in grouped:
            models_used.append({
                "model_name": name, "model_version": version, "rows_scored": int(len(part)),
                "anomalies": int(part["is_anomaly"].sum()), "anomaly_rate": float(part["is_anomaly"].mean()),
                "last_scored_at": str(part["created_at"].max()),
            })
    last_run = inference_runs[0] if inference_runs else None
    return {
        "rows_scored": total,
        "anomalies": anomalies,
        "normal": total - anomalies,
        "anomaly_rate": (anomalies / total) if total else None,
        "models_used": models_used,
        "last_detection_at": str(frame["created_at"].max()) if total else None,
        "last_run": {k: last_run.get(k) for k in ("run_id", "status", "dataset_id", "batch_id", "model_name",
                                                   "started_at", "finished_at", "error")} if last_run else None,
        "registry": {
            "models": len(registry),
            "versions": sum(len(m["versions"]) for m in registry),
            "production": [{"model_name": m["model_name"], "version": m["production_version"]}
                           for m in registry if m["production_version"]],
        },
        "score_note": SCORE_NOTE,
    }


def _select_model(frame: pd.DataFrame, model_name, model_version) -> tuple[pd.DataFrame, dict]:
    """Оставляет предсказания одной модели/версии, чтобы не смешивать шкалы score."""
    available = (
        frame.groupby(["model_name", "model_version"])["created_at"].max().reset_index()
        .sort_values("created_at", ascending=False)
    )
    if available.empty:
        return frame, {}
    # Явно заданные model_name/version уже отфильтрованы в read_predictions; иначе берём последнюю по времени.
    chosen = available.iloc[0]
    selected = frame[(frame["model_name"] == chosen["model_name"]) & (frame["model_version"] == chosen["model_version"])]
    return selected, {
        "model_name": chosen["model_name"], "model_version": chosen["model_version"],
        "available": [{"model_name": r["model_name"], "model_version": r["model_version"]}
                      for _, r in available.iterrows()],
    }


def anomalies_summary(dataset_id=None, batch_id=None, model_name=None, model_version=None, bins=20) -> dict:
    dataset_id, batch_id = safe_id(dataset_id, "dataset_id"), safe_id(batch_id, "batch_id")
    frame = _predictions(dataset_id, batch_id, model_name, model_version, columns=_PRED_COLUMNS)
    empty = {"model": None, "rows_scored": 0, "anomalies": 0, "by_station": [], "by_batch": [],
             "score_histogram": None, "by_feature": [], "score_note": SCORE_NOTE}
    if frame.empty:
        return empty
    frame, model = _select_model(frame, model_name, model_version)

    def breakdown(key: str) -> list[dict]:
        part = frame.assign(_key=frame[key].fillna("—").astype(str)).groupby("_key")["is_anomaly"].agg(["sum", "count"])
        return [{"key": k, "anomalies": int(r["sum"]), "total": int(r["count"]),
                 "rate": float(r["sum"] / r["count"])} for k, r in part.sort_values("sum", ascending=False).iterrows()]

    scores = frame["anomaly_score"].to_numpy(dtype="float64")
    edges = np.histogram_bin_edges(scores, bins=bins)
    flags = frame["is_anomaly"].to_numpy(dtype=bool)
    histogram = {
        "edges": [float(e) for e in edges],
        "normal": [int(c) for c in np.histogram(scores[~flags], bins=edges)[0]],
        "anomaly": [int(c) for c in np.histogram(scores[flags], bins=edges)[0]],
    }

    features = Counter()
    contexts = _predictions(dataset_id, batch_id, model["model_name"], model["model_version"],
                            columns=["context", "is_anomaly"], only_anomalies=True)
    for raw in (contexts["context"].head(5000) if not contexts.empty else []):
        try:
            top = json.loads(raw)["top_features"]
        except (TypeError, ValueError, KeyError):
            continue
        if top:
            features[top[0]["feature"]] += 1

    return {
        "model": model,
        "rows_scored": int(len(frame)),
        "anomalies": int(flags.sum()),
        "by_station": breakdown("station_id"),
        "by_batch": breakdown("batch_id"),
        "score_histogram": histogram,
        # Признак с наибольшим отклонением у аномалии (top-1); производные признаки сведены к исходному параметру.
        "by_feature": [{"feature": f, "parameter": _DERIVED_SUFFIX.sub("", f), "anomalies": c}
                       for f, c in features.most_common()],
        "score_note": SCORE_NOTE,
    }


def _joined(dataset_id, batch_id, model_name, model_version, parameters: list[str] | None):
    dataset_id, batch_id = safe_id(dataset_id, "dataset_id"), safe_id(batch_id, "batch_id")
    if not dataset_id or not batch_id:
        raise ApiError("INVALID_PARAMETER", "Нужны dataset_id и batch_id", 422)
    predictions = _predictions(dataset_id, batch_id, model_name, model_version)
    if predictions.empty:
        raise ApiError("PREDICTIONS_NOT_FOUND", "Для batch нет результатов детекции", 404,
                       {"dataset_id": dataset_id, "batch_id": batch_id})
    predictions, model = _select_model(predictions, model_name, model_version)
    predictions = predictions.drop_duplicates("record_id")

    manifest = analytics_root() / "manifests" / f"dataset_id={dataset_id}" / f"batch_id={batch_id}.json"
    try:
        if manifest.is_file():
            mapping = json.loads(manifest.read_text(encoding="utf-8"))["mapping"]
            known = mapping.get("parameter_columns") or []
            wanted = [p for p in (parameters or known[:8]) if p in known]
            columns = ["_record_hash", "_source_row_number", mapping.get("timestamp_column"),
                       mapping.get("station_column"), *wanted]
            gold, _ = load_curated(dataset_id, batch_id, columns=[c for c in dict.fromkeys(columns) if c])
        else:
            gold, _ = load_curated(dataset_id, batch_id)
            detected = detect_mapping(gold)
            mapping = {"timestamp_column": detected.timestamp_column, "station_column": detected.station_column,
                       "parameter_columns": detected.parameter_columns}
            known = mapping["parameter_columns"] or []
            wanted = [p for p in (parameters or known[:8]) if p in known]
    except DataNotReadyError as error:
        raise ApiError("DATA_NOT_READY", error.message, 409, error.details) from error
    except (KeyError, FileNotFoundError, OSError) as error:
        raise ApiError("DATA_NOT_READY", "Gold-данные для batch недоступны", 409) from error

    for name in parameters or []:
        if name not in known:
            raise ApiError("UNKNOWN_PARAMETER", "Параметр не найден в наборе данных", 422, {"parameter": name})

    if "_record_hash" in gold.columns:
        joined = gold.merge(predictions, left_on="_record_hash", right_on="record_id", how="inner", suffixes=("", "_p"))
    elif "_source_row_number" in gold.columns:
        joined = gold.merge(predictions, left_on="_source_row_number", right_on="source_row_number",
                            how="inner", suffixes=("", "_p"))
    else:
        raise ApiError("DATA_NOT_READY", "В Gold нет ключа записи для сопоставления с предсказаниями", 409)
    return joined, mapping, model, wanted


def _stamp(joined: pd.DataFrame, mapping: dict) -> tuple[pd.Series, str]:
    column = mapping.get("timestamp_column")
    if column and column in joined.columns:
        return pd.to_datetime(joined[column], errors="coerce", utc=True), "time"
    key = "_source_row_number" if "_source_row_number" in joined.columns else None
    return (joined[key] if key else pd.Series(range(len(joined)), index=joined.index)), "row_number"


def _station_filter(joined, mapping, station_id):
    if not station_id:
        return joined
    column = mapping.get("station_column")
    if not column or column not in joined.columns:
        raise ApiError("FILTER_NOT_SUPPORTED", "В наборе данных нет колонки станции", 422, {"filter": "station_id"})
    return joined[joined[column].astype(str) == station_id]


def _thin(frame: pd.DataFrame, limit: int) -> tuple[pd.DataFrame, bool]:
    if len(frame) <= limit:
        return frame, False
    step = math.ceil(len(frame) / limit)
    return frame.iloc[::step], True


def anomaly_series(dataset_id, batch_id, parameter, station_id=None, model_name=None,
                   model_version=None, max_points=5000) -> dict:
    joined, mapping, model, _ = _joined(dataset_id, batch_id, model_name, model_version, [parameter])
    joined = _station_filter(joined, mapping, safe_id(station_id, "station_id"))
    x, x_kind = _stamp(joined, mapping)
    values = pd.to_numeric(joined[parameter], errors="coerce")
    data = pd.DataFrame({"x": x, "value": values, "score": joined["anomaly_score"],
                         "is_anomaly": joined["is_anomaly"].astype(bool),
                         "station": joined[mapping["station_column"]].astype(str)
                         if mapping.get("station_column") in joined.columns else None})
    data = data.dropna(subset=["x", "value"]).sort_values("x")
    normal, thinned = _thin(data[~data["is_anomaly"]], max_points)
    flagged = data[data["is_anomaly"]]

    def points(part: pd.DataFrame) -> list[dict]:
        return [{
            "x": row.x.isoformat() if x_kind == "time" else int(row.x),
            "value": float(row.value), "score": number(row.score),
            "station": row.station if isinstance(row.station, str) else None,
        } for row in part.itertuples()]

    return {
        "dataset_id": dataset_id, "batch_id": batch_id, "parameter": parameter, "model": model,
        "x_kind": x_kind, "normal": points(normal), "anomalies": points(flagged),
        "total_points": int(len(data)), "downsampled": thinned, "score_note": SCORE_NOTE,
    }


def anomaly_scatter(dataset_id, batch_id, parameter_x, parameter_y, station_id=None, model_name=None,
                    model_version=None, max_points=3000) -> dict:
    joined, mapping, model, _ = _joined(dataset_id, batch_id, model_name, model_version, [parameter_x, parameter_y])
    joined = _station_filter(joined, mapping, safe_id(station_id, "station_id"))
    data = pd.DataFrame({
        "x": pd.to_numeric(joined[parameter_x], errors="coerce"),
        "y": pd.to_numeric(joined[parameter_y], errors="coerce"),
        "is_anomaly": joined["is_anomaly"].astype(bool),
    }).dropna(subset=["x", "y"])
    normal, thinned = _thin(data[~data["is_anomaly"]], max_points)
    return {
        "dataset_id": dataset_id, "batch_id": batch_id, "parameter_x": parameter_x, "parameter_y": parameter_y,
        "model": model, "normal": normal[["x", "y"]].to_dict("records"),
        "anomalies": data[data["is_anomaly"]][["x", "y"]].to_dict("records"),
        "total_points": int(len(data)), "downsampled": thinned,
    }


def anomaly_records(dataset_id, batch_id, station_id=None, model_name=None, model_version=None,
                    limit=50, offset=0) -> dict:
    joined, mapping, model, wanted = _joined(dataset_id, batch_id, model_name, model_version, None)
    joined = _station_filter(joined, mapping, safe_id(station_id, "station_id"))
    flagged = joined[joined["is_anomaly"].astype(bool)].sort_values("anomaly_score")
    x, x_kind = _stamp(flagged, mapping)
    contexts = _predictions(dataset_id, batch_id, model["model_name"], model["model_version"],
                            columns=["record_id", "context"], only_anomalies=True)
    top = {}
    for row in contexts.itertuples():
        try:
            top[row.record_id] = json.loads(row.context)["top_features"][0]
        except (TypeError, ValueError, KeyError, IndexError):
            continue

    items = []
    for index, row in flagged.iloc[offset: offset + limit].iterrows():
        items.append({
            "prediction_id": row["prediction_id"],
            "measured_at": x.loc[index].isoformat() if x_kind == "time" and pd.notna(x.loc[index]) else None,
            "row_number": int(row["_source_row_number"]) if "_source_row_number" in row and pd.notna(row["_source_row_number"]) else None,
            "station_id": str(row[mapping["station_column"]]) if mapping.get("station_column") in row else None,
            "values": {name: number(row[name]) for name in wanted},
            "anomaly_score": number(row["anomaly_score"]),
            "model_name": row["model_name"], "model_version": row["model_version"],
            "top_feature": top.get(row["record_id"]),
        })
    return {"items": items, "total": int(len(flagged)), "model": model, "parameters": wanted, "score_note": SCORE_NOTE}


def model_detail(model_name: str) -> dict:
    registry = ModelRegistry()
    try:
        versions = registry.list_versions(model_name)
    except RegistryError as error:
        raise ApiError("INVALID_MODEL_NAME", str(error), 400) from error
    if not versions:
        raise ApiError("MODEL_NOT_FOUND", "Модель не найдена", 404, {"model_name": model_name})

    history = []
    for path in (_lake() / "predictions").glob(f"model_name={model_name}/model_version=*/dataset_id=*/batch_id=*/summary.json"):
        try:
            history.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    history.sort(key=lambda item: item.get("created_at") or "", reverse=True)

    out = []
    for version in versions:
        evaluation = version.get("evaluation") or {}
        supervised = evaluation.get("supervised")
        out.append({
            "model_version": version["model_version"], "status": version["status"],
            "algorithm": version.get("algorithm"), "params": version.get("params"),
            "features": version.get("features"), "feature_config": version.get("feature_config"),
            "feature_version": version.get("feature_version"),
            "created_at": version.get("created_at"), "approved_by": version.get("approved_by"),
            "comments": version.get("comments", []),
            "training": {k: version.get(k) for k in ("dataset_id", "batch_id", "rows_total", "rows_train",
                                                     "train_period", "test_period", "code_version",
                                                     "training_run_id", "quality_status")},
            "evaluation": evaluation,
            # Precision/Recall/ROC-AUC существуют только если модель оценивали на размеченном столбце.
            "ground_truth_metrics": supervised if supervised and "precision" in supervised else None,
            "has_ground_truth": bool(supervised and "precision" in supervised),
        })
    production = [v for v in versions if v["status"] == "production"]
    return {"model_name": model_name, "active_version": production[-1]["model_version"] if production else None,
            "versions": out, "detection_history": history}


def drift(model_name=None, dataset_id=None) -> dict:
    dataset_id = safe_id(dataset_id, "dataset_id")
    root = _lake() / "monitoring" / "ml"
    reports = []
    for path in root.glob("model_name=*/dataset_id=*/batch_id=*.json"):
        parts = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in path.parts if "=" in p}
        if model_name and parts.get("model_name") != model_name:
            continue
        if dataset_id and parts.get("dataset_id") != dataset_id:
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        generated = report.get("generated_at")
        if not generated:  # отчёты, созданные до появления generated_at
            from datetime import datetime, timezone
            generated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
            report["generated_at_source"] = "file_mtime"
        features = report.get("feature_drift", {})
        psi_values = [f["psi"] for f in features.values() if f.get("psi") is not None]
        reports.append({
            "dataset_id": report.get("dataset_id", parts.get("dataset_id")),
            "batch_id": report.get("batch_id", parts.get("batch_id")),
            "model_name": report.get("model_name", parts.get("model_name")),
            "model_version": report.get("model_version"),
            "generated_at": generated,
            "generated_at_source": report.get("generated_at_source", "report"),
            "overall_status": report.get("overall_status"),
            "max_psi": max(psi_values) if psi_values else None,
            "drifted_features": report.get("drifted_features", []),
            "feature_drift": features,
            "anomaly_rate": report.get("anomaly_rate"),
            "anomaly_rate_vs_contamination": report.get("anomaly_rate_vs_contamination"),
        })
    reports.sort(key=lambda item: item["generated_at"])
    return {
        "available": bool(reports),
        "thresholds": {"warning": PSI_WARNING, "alert": PSI_ALERT, "source": "backend/ml/monitoring.py"},
        "reports": reports,
        "latest": reports[-1] if reports else None,
    }
