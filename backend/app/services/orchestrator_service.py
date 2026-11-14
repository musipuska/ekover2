import logging

import httpx

from backend.app.core.config import settings
from backend.app.core.exceptions import StorageError
from backend.app.infrastructure.database.models import ETLJob
from backend.app.infrastructure.database.session import SessionLocal

logger = logging.getLogger(__name__)


def trigger_airflow_dag(dag_id: str, conf: dict, dag_run_id: str | None = None) -> dict:
    payload = {"conf": conf}
    if dag_run_id:
        payload["dag_run_id"] = dag_run_id
    try:
        response = httpx.post(
            f"{settings.AIRFLOW_API_URL.rstrip('/')}/dags/{dag_id}/dagRuns",
            json=payload,
            auth=(settings.AIRFLOW_USERNAME, settings.AIRFLOW_PASSWORD),
            timeout=settings.AIRFLOW_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise StorageError(f"Не удалось запустить DAG {dag_id}: {error}") from error
    return response.json()


def start_etl_via_airflow(dataset_id: str, version_id: str, job_id: str, batch_id: str) -> None:
    conf = {
        "dataset_id": dataset_id,
        "version_id": version_id,
        "job_id": job_id,
        "batch_id": batch_id,
    }
    db = SessionLocal()
    try:
        try:
            run = trigger_airflow_dag(
                settings.AIRFLOW_ETL_DAG_ID, conf, dag_run_id=f"api__{job_id}"
            )
        except StorageError as error:
            logger.exception("Airflow trigger failed: job_id=%s", job_id)
            job = db.query(ETLJob).filter(ETLJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(error)
                db.commit()
            return

        job = db.query(ETLJob).filter(ETLJob.id == job_id).first()
        if job:
            job.orchestrator_run_id = run.get("dag_run_id")
            db.commit()
    finally:
        db.close()
