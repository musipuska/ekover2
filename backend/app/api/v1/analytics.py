from fastapi import APIRouter, Query

from backend.analytics import repository
from backend.app.api.envelope import ApiError, ok
from backend.app.services import gold_reader

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview")
def get_overview():
    return ok(repository.overview())


@router.get("/datasets")
def get_datasets(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    page = repository.dataset_summaries(limit=limit, offset=offset)
    return ok(page["items"], total=page["total"], limit=limit, offset=offset)


@router.get("/datasets/{dataset_id}/parameters")
def get_parameters(dataset_id: str, batch_id: str | None = None):
    items = repository.parameter_metrics(dataset_id, batch_id)
    if not items:
        raise ApiError("ANALYTICS_NOT_FOUND", "Витрины для набора данных не построены", 404, {"dataset_id": dataset_id})
    return ok(items)


@router.get("/datasets/{dataset_id}/stations")
def get_stations(dataset_id: str, batch_id: str | None = None, parameter: str | None = None):
    return ok(repository.station_metrics(dataset_id, batch_id, parameter))


@router.get("/datasets/{dataset_id}/trends")
def get_trends(
    dataset_id: str,
    parameter: str,
    station_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    batch_id: str | None = None,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    page = repository.trends(dataset_id, parameter, station_id, date_from, date_to, batch_id, limit, offset)
    return ok(page["items"], total=page["total"], limit=limit, offset=offset)


@router.get("/datasets/{dataset_id}/quality")
def get_quality_history(dataset_id: str):
    return ok(gold_reader.list_batches(dataset_id))
