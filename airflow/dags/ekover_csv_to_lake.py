"""Airflow orchestration for the existing ЭКОВЕР Spark ETL pipeline.

Trigger this DAG with dag_run.conf containing:
{
  "dataset_id": "...",
  "version_id": "...",
  "job_id": "...",
  "batch_id": "..."
}
The repository root must be available on PYTHONPATH in the Airflow worker.
"""
from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator

from airflow import DAG

REQUIRED_CONF_KEYS = ("dataset_id", "version_id", "job_id", "batch_id")


def run_ekover_etl(**context) -> None:
    """Validate the trigger payload and delegate processing to the existing ETL."""
    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}

    missing = [
        key for key in REQUIRED_CONF_KEYS
        if not isinstance(conf.get(key), str) or not conf[key].strip()
    ]
    if missing:
        raise AirflowException(
            "Missing or empty DAG run configuration fields: "
            + ", ".join(missing)
        )

    # Import lazily so the DAG can be parsed without eagerly importing Spark
    # and the application database stack in the scheduler.
    from backend.etl.jobs.csv_to_lake import run_etl

    run_etl(
        dataset_id=conf["dataset_id"],
        version_id=conf["version_id"],
        job_id=conf["job_id"],
        batch_id=conf["batch_id"],
    )


with DAG(
    dag_id="ekover_csv_to_lake",
    description="Orchestrate the existing ЭКОВЕР CSV → Bronze → Silver → Gold pipeline",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "ekover",
        "retries": 2,
        "retry_delay": timedelta(minutes=3),
    },
    tags=["ekover", "spark", "etl", "data-quality"],
) as dag:
    process_dataset = PythonOperator(
        task_id="process_dataset",
        python_callable=run_ekover_etl,
    )
