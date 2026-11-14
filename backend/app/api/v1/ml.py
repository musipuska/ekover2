import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel, Field

from backend.app.api.envelope import ApiError, ok
from backend.ml.features import FeatureConfig
from backend.ml.inference import batch_predict, read_predictions
from backend.ml.registry import ModelRegistry, RegistryError
from backend.ml.training import DEFAULT_MODEL_NAME, read_run, save_run, train_model

router = APIRouter(prefix="/ml", tags=["ML"])


class TrainingRequest(BaseModel):
    dataset_id: str
    batch_id: str
    model_name: str = DEFAULT_MODEL_NAME
    contamination: float = Field(0.02, gt=0, le=0.5)
    feature_config: dict = {}


class InferenceRequest(BaseModel):
    dataset_id: str
    batch_id: str
    model_name: str = DEFAULT_MODEL_NAME
    model_version: str | None = None
    allow_candidate: bool = False


class StatusChange(BaseModel):
    status: str
    approved_by: str | None = None
    comment: str | None = None


def _slim(model: dict) -> dict:
    versions = [
        {key: value for key, value in item.items() if key != "feature_stats"}
        for item in model["versions"]
    ]
    return {**model, "versions": versions}


@router.get("/models")
def list_models():
    return ok([_slim(item) for item in ModelRegistry().list_models()])


@router.get("/models/{model_name}")
def get_model(model_name: str):
    try:
        versions = ModelRegistry().list_versions(model_name)
    except RegistryError as error:
        raise ApiError("INVALID_MODEL_NAME", str(error), 400) from error
    if not versions:
        raise ApiError("MODEL_NOT_FOUND", "Модель не найдена", 404, {"model_name": model_name})
    return ok([{k: v for k, v in item.items() if k != "feature_stats"} for item in versions])


@router.post("/models/{model_name}/versions/{version}/status")
def change_status(model_name: str, version: str, body: StatusChange):
    try:
        metadata = ModelRegistry().set_status(model_name, version, body.status, body.approved_by, body.comment)
    except RegistryError as error:
        raise ApiError("MODEL_STATUS_REJECTED", str(error), 409) from error
    return ok({k: v for k, v in metadata.items() if k != "feature_stats"})


def _records(frame, limit: int, offset: int) -> list[dict]:
    page = frame.iloc[offset: offset + limit]
    items = json.loads(page.to_json(orient="records"))
    for item in items:
        if isinstance(item.get("context"), str):
            item["context"] = json.loads(item["context"])
    return items


@router.get("/predictions")
def list_predictions(
    dataset_id: str | None = None,
    batch_id: str | None = None,
    model_name: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    frame = read_predictions(model_name, dataset_id, batch_id)
    return ok(_records(frame, limit, offset), total=int(len(frame)), limit=limit, offset=offset)


@router.get("/anomalies")
def list_anomalies(
    dataset_id: str | None = None,
    batch_id: str | None = None,
    model_name: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    frame = read_predictions(model_name, dataset_id, batch_id, only_anomalies=True)
    return ok(_records(frame, limit, offset), total=int(len(frame)), limit=limit, offset=offset)


@router.get("/anomalies/{prediction_id}")
def get_anomaly(prediction_id: str):
    frame = read_predictions(only_anomalies=False)
    match = frame[frame["prediction_id"] == prediction_id] if len(frame) else frame
    if match.empty:
        raise ApiError("PREDICTION_NOT_FOUND", "Предсказание не найдено", 404)
    return ok(_records(match, 1, 0)[0])


def _run_training(run_id: str, body: TrainingRequest) -> None:
    try:
        train_model(
            body.dataset_id,
            body.batch_id,
            model_name=body.model_name,
            config=FeatureConfig.from_dict(body.feature_config),
            contamination=body.contamination,
            run_id=run_id,
        )
    except Exception:
        pass


def _run_inference(run_id: str, body: InferenceRequest) -> None:
    from datetime import datetime, timezone

    record = {
        "run_id": run_id,
        "kind": "inference",
        "dataset_id": body.dataset_id,
        "batch_id": body.batch_id,
        "model_name": body.model_name,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        summary = batch_predict(
            body.dataset_id, body.batch_id, body.model_name,
            body.model_version, body.allow_candidate,
        )
        record.update(status="completed", summary=summary)
    except Exception as error:
        record.update(status="failed", error=str(error))
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    save_run(record)


@router.post("/training-runs", status_code=202)
def create_training_run(body: TrainingRequest, background: BackgroundTasks):
    run_id = uuid.uuid4().hex
    save_run({"run_id": run_id, "kind": "training", "status": "queued", **body.model_dump(exclude={"feature_config"})})
    background.add_task(_run_training, run_id, body)
    return ok({"job_id": run_id, "status": "queued"})


@router.post("/inference", status_code=202)
def create_inference(body: InferenceRequest, background: BackgroundTasks):
    run_id = uuid.uuid4().hex
    save_run({"run_id": run_id, "kind": "inference", "status": "queued", **body.model_dump()})
    background.add_task(_run_inference, run_id, body)
    return ok({"job_id": run_id, "status": "queued"})


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    record = read_run(run_id)
    if record is None:
        raise ApiError("RUN_NOT_FOUND", "Запуск не найден", 404)
    return ok(record)
