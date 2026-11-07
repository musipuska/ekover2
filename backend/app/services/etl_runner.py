
import logging
import subprocess
import sys

from pathlib import Path

from backend.app.infrastructure.database.session import SessionLocal
from backend.app.infrastructure.database.models import ETLJob


logger = logging.getLogger(__name__)

# Корневая папка проекта ekover_starter
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def start_etl_process(
    dataset_id: str,
    version_id: str,
    job_id: str,
    batch_id: str,
) -> None:
    """
    Запускает ETL в отдельном процессе Python.
    """

    log_directory = PROJECT_ROOT / "data" / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)

    log_path = log_directory / f"etl_{job_id}.log"

    command = [
        sys.executable,
        "-m",
        "backend.etl.jobs.csv_to_lake",
        "--dataset-id", dataset_id,
        "--version-id", version_id,
        "--job-id", job_id,
        "--batch-id", batch_id,
    ]

    try:
        with log_path.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        logger.info(
            "ETL process started: job_id=%s pid=%s",
            job_id,
            process.pid,
        )

    except Exception as error:
        logger.exception(
            "Не удалось запустить ETL: job_id=%s",
            job_id,
        )

        db = SessionLocal()

        try:
            job = db.query(ETLJob).filter(
                ETLJob.id == job_id
            ).first()

            if job:
                job.status = "failed"
                job.error_message = (
                    f"Не удалось запустить ETL: {error}"
                )
                db.commit()

        finally:
            db.close()
