from backend.analytics.marts import AnalyticsMapping, build_marts, validate_marts
from backend.ml.data import load_curated
from backend.etl.common.metadata import track_stage


def _required(conf: dict) -> tuple[str, str]:
    for key in ("dataset_id", "batch_id"):
        if not isinstance(conf.get(key), str) or not conf[key].strip():
            raise ValueError(f"Missing or empty DAG run configuration field: {key}")
    return conf["dataset_id"], conf["batch_id"]


def _mapping(conf: dict) -> AnalyticsMapping | None:
    raw = conf.get("mapping")
    return AnalyticsMapping(**raw) if raw else None


@track_stage("analytics")
def task_check_gold(conf: dict) -> dict:
    dataset_id, batch_id = _required(conf)
    frame, manifest = load_curated(dataset_id, batch_id)
    return {"rows": int(len(frame)), "quality_status": manifest.get("quality_status")}


@track_stage("analytics")
def task_build_marts(conf: dict) -> dict:
    dataset_id, batch_id = _required(conf)
    summary = build_marts(dataset_id, batch_id, _mapping(conf))
    return {name: info["rows"] for name, info in summary["marts"].items()}


@track_stage("analytics")
def task_validate_marts(conf: dict) -> dict:
    dataset_id, batch_id = _required(conf)
    return validate_marts(
        dataset_id,
        batch_id,
        mapping=_mapping(conf),
    )