from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.analytics import executive, ml_stats, pipeline_stats, quality_stats, repository, water_stats
from backend.app.api.envelope import ApiError, ok
from backend.app.infrastructure.database.session import get_db
from backend.app.schemas import analytics as schemas
from backend.app.services import gold_reader

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _respond(schema: type[BaseModel], data: dict, **extra) -> dict:
    """Проверяет ответ по контракту и упаковывает в envelope."""
    return ok(schema.model_validate(data).model_dump(mode="json"), **extra)


# --- Существующие endpoints (контракты не менялись) ---------------------------

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


# --- Overview dashboard --------------------------------------------------------

@router.get("/summary")
def get_summary(
    dataset_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    return _respond(schemas.ExecutiveSummary, executive.summary(db, dataset_id, date_from, date_to))


# --- Water quality dashboard ---------------------------------------------------

@router.get("/water/catalog")
def get_water_catalog(dataset_id: str, batch_id: str | None = None):
    return _respond(schemas.WaterCatalog, water_stats.catalog(dataset_id, batch_id))


@router.get("/water/distribution")
def get_distribution(
    dataset_id: str,
    parameter: str,
    batch_id: str | None = None,
    station_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    bins: int = Query(20, ge=2, le=100),
):
    return _respond(
        schemas.Distribution,
        water_stats.distribution(dataset_id, parameter, batch_id, station_id, date_from, date_to, bins),
    )


@router.get("/water/correlation")
def get_correlation(
    dataset_id: str,
    batch_id: str | None = None,
    station_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    method: Literal["pearson", "spearman"] = "pearson",
    min_periods: int = Query(10, ge=3, le=10000),
):
    return _respond(
        schemas.Correlation,
        water_stats.correlation(dataset_id, batch_id, station_id, date_from, date_to, method, min_periods),
    )


@router.get("/water/thresholds")
def get_thresholds():
    return _respond(schemas.Thresholds, water_stats.thresholds())


@router.get("/water/measurements")
def get_measurements(
    dataset_id: str,
    parameter: str,
    batch_id: str | None = None,
    station_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    data = water_stats.measurements(dataset_id, parameter, batch_id, station_id, date_from, date_to, limit, offset)
    return _respond(schemas.Measurements, data, total=data["total"], limit=limit, offset=offset)


# --- Data quality dashboard ----------------------------------------------------

@router.get("/quality/overview")
def get_quality_overview(
    dataset_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    return _respond(schemas.QualityOverview, quality_stats.overview(db, dataset_id, date_from, date_to))


@router.get("/quality/rules")
def get_quality_rules(
    dataset_id: str | None = None,
    batch_id: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    rule_type: str | None = None,
    search: str | None = Query(None, max_length=100),
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    data = quality_stats.rules(
        db, dataset_id, batch_id, status, severity, rule_type, search, sort_by, sort_dir, limit, offset,
        date_from, date_to,
    )
    return _respond(schemas.QualityRules, data, total=data["total"], limit=limit, offset=offset)


@router.get("/quality/columns")
def get_quality_columns(dataset_id: str, batch_id: str | None = None):
    return _respond(schemas.QualityColumns, quality_stats.columns(dataset_id, batch_id))


# --- ML dashboard ----------------------------------------------------------------

@router.get("/ml/overview")
def get_ml_overview(dataset_id: str | None = None, date_from: str | None = None, date_to: str | None = None):
    return _respond(schemas.MlOverview, ml_stats.overview(dataset_id, date_from, date_to))


@router.get("/ml/anomalies/summary")
def get_anomalies_summary(
    dataset_id: str | None = None,
    batch_id: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
):
    return _respond(
        schemas.AnomaliesSummary, ml_stats.anomalies_summary(dataset_id, batch_id, model_name, model_version)
    )


@router.get("/ml/anomalies/series")
def get_anomaly_series(
    dataset_id: str,
    batch_id: str,
    parameter: str,
    station_id: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    max_points: int = Query(5000, ge=100, le=20000),
):
    return _respond(
        schemas.AnomalySeries,
        ml_stats.anomaly_series(dataset_id, batch_id, parameter, station_id, model_name, model_version, max_points),
    )


@router.get("/ml/anomalies/scatter")
def get_anomaly_scatter(
    dataset_id: str,
    batch_id: str,
    parameter_x: str,
    parameter_y: str,
    station_id: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    max_points: int = Query(3000, ge=100, le=20000),
):
    return _respond(
        schemas.AnomalyScatter,
        ml_stats.anomaly_scatter(
            dataset_id, batch_id, parameter_x, parameter_y, station_id, model_name, model_version, max_points
        ),
    )


@router.get("/ml/anomalies/records")
def get_anomaly_records(
    dataset_id: str,
    batch_id: str,
    station_id: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    data = ml_stats.anomaly_records(dataset_id, batch_id, station_id, model_name, model_version, limit, offset)
    return _respond(schemas.AnomalyRecords, data, total=data["total"], limit=limit, offset=offset)


@router.get("/ml/models/{model_name}")
def get_model_detail(model_name: str):
    return _respond(schemas.ModelDetail, ml_stats.model_detail(model_name))


@router.get("/ml/runs")
def get_ml_runs(
    kind: str | None = None,
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    return _respond(schemas.MlRuns, ml_stats.runs(kind, status, limit))


@router.get("/ml/drift")
def get_drift(model_name: str | None = None, dataset_id: str | None = None):
    return _respond(schemas.Drift, ml_stats.drift(model_name, dataset_id))


# --- ETL & pipeline dashboard ---------------------------------------------------

@router.get("/pipeline/overview")
def get_pipeline_overview(
    dataset_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    return _respond(schemas.PipelineOverview, pipeline_stats.overview(db, dataset_id, date_from, date_to))


@router.get("/pipeline/performance")
def get_pipeline_performance(
    dataset_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    return _respond(schemas.PipelinePerformance, pipeline_stats.performance(db, dataset_id, date_from, date_to))


@router.get("/pipeline/jobs")
def get_pipeline_jobs(
    dataset_id: str | None = None,
    status: str | None = None,
    search: str | None = Query(None, max_length=100),
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    data = pipeline_stats.list_jobs(
        db, dataset_id, date_from, date_to, status, search, sort_by, sort_dir, limit, offset
    )
    return _respond(schemas.JobsPage, data, total=data["total"], limit=limit, offset=offset)


@router.get("/pipeline/jobs/{job_id}")
def get_pipeline_job(job_id: str, db: Session = Depends(get_db)):
    return _respond(schemas.JobDetail, pipeline_stats.job_detail(db, job_id))


@router.get("/pipeline/errors")
def get_pipeline_errors(
    dataset_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return _respond(schemas.ErrorsPage, pipeline_stats.errors(db, dataset_id, date_from, date_to, limit))
