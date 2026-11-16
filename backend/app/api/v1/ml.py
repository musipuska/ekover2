import hashlib
import hmac
import json
import logging
import traceback
import uuid

from fastapi import APIRouter, BackgroundTasks, Header, Query
from pydantic import BaseModel, Field

from backend.app.api.envelope import ApiError, ok
from backend.app.core.config import settings
from backend.ml.features import FeatureConfig
from backend.ml.inference import batch_predict, read_predictions
from backend.ml.registry import ModelRegistry, RegistryError
from backend.ml.training import DEFAULT_MODEL_NAME, read_run, save_run, train_model

router = APIRouter(prefix="/ml", tags=["ML"])
logger = logging.getLogger(__name__)


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
    comment: str | None = None


def require_admin(x_api_key: str | None) -> str:
    """Проверяет ключ администратора и возвращает идентификатор утверждающего."""
    configured = settings.ADMIN_API_KEY
    if not configured:
        raise ApiError("ADMIN_DISABLED", "Смена статуса модели отключена: ADMIN_API_KEY не задан", 403)
    if not x_api_key or not hmac.compare_digest(x_api_key, configured):
        raise ApiError("FORBIDDEN", "Неверный или отсутствующий API-ключ", 403)
    return "admin:" + hashlib.sha256(configured.encode("utf-8")).hexdigest()[:8]


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
def change_status(
    model_name: str,
    version: str,
    body: StatusChange,
    x_api_key: str | None = Header(default=None),
):
    approver = require_admin(x_api_key)
    try:
        metadata = ModelRegistry().set_status(model_name, version, body.status, approver, body.comment)
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
        # train_model уже записал run со статусом failed и текстом ошибки;
        # здесь сохраняем traceback в лог и в run-запись.
        trace = traceback.format_exc()
        logger.error("Training run %s failed\n%s", run_id, trace)
        record = read_run(run_id) or {"run_id": run_id, "kind": "training", "status": "failed"}
        record["traceback"] = trace
        save_run(record)


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
        logger.exception("Inference run %s failed", run_id)
        record.update(status="failed", error=str(error), traceback=traceback.format_exc())
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
