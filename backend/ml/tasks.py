from backend.ml.features import FeatureConfig
from backend.ml.inference import batch_predict, read_predictions
from backend.ml.monitoring import monitor_batch
from backend.ml.training import DEFAULT_MODEL_NAME, train_model
from backend.etl.common.metadata import track_stage


def _config(conf: dict) -> FeatureConfig:
    return FeatureConfig.from_dict(conf.get("feature_config") or {})


def _required(conf: dict) -> tuple[str, str]:
    for key in ("dataset_id", "batch_id"):
        if not isinstance(conf.get(key), str) or not conf[key].strip():
            raise ValueError(f"Missing or empty DAG run configuration field: {key}")
    return conf["dataset_id"], conf["batch_id"]


@track_stage("ml")
def task_check_data(conf: dict) -> dict:
    from backend.ml.data import load_curated

    dataset_id, batch_id = _required(conf)
    frame, manifest = load_curated(dataset_id, batch_id)
    return {"rows": int(len(frame)), "quality_status": manifest.get("quality_status")}


@track_stage("ml")
def task_train(conf: dict) -> dict:
    dataset_id, batch_id = _required(conf)
    record = train_model(
        dataset_id,
        batch_id,
        model_name=conf.get("model_name", DEFAULT_MODEL_NAME),
        config=_config(conf),
        contamination=float(conf.get("contamination", 0.02)),
    )
    return {"model_version": record["model_version"], "run_id": record["run_id"]}


@track_stage("ml")
def task_inference(conf: dict, trained_version: str | None = None) -> dict:
    dataset_id, batch_id = _required(conf)
    summary = batch_predict(
        dataset_id,
        batch_id,
        conf.get("model_name", DEFAULT_MODEL_NAME),
        model_version=trained_version or conf.get("model_version"),
        allow_candidate=bool(trained_version) or bool(conf.get("allow_candidate", False)),
    )
    return {key: summary[key] for key in ("model_version", "rows_scored", "anomaly_count", "anomaly_rate")}


@track_stage("ml")
def task_monitor(conf: dict, model_version: str | None = None) -> dict:
    dataset_id, batch_id = _required(conf)
    name = conf.get("model_name", DEFAULT_MODEL_NAME)
    version = model_version or conf.get("model_version")
    predictions = read_predictions(name, dataset_id, batch_id)
    if version and len(predictions):
        predictions = predictions[predictions["model_version"] == version]
    report = monitor_batch(
        dataset_id,
        batch_id,
        name,
        model_version=version,
        allow_candidate=True,
        predictions=predictions,
    )
    return {"overall_status": report["overall_status"], "drifted_features": report["drifted_features"]}
