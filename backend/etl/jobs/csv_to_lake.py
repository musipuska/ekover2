import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
import json
import traceback

from pyspark.sql import SparkSession

from backend.app.core.config import settings
from backend.app.infrastructure.database.session import SessionLocal
from backend.app.infrastructure.database.models import (
    DatasetVersion,
    ETLJob,
)

from backend.etl.transformations.bronze import (
    create_bronze_layer,
)
from backend.etl.transformations.silver import (
    clean_silver_layer,
    save_silver_layer,
)
from backend.etl.transformations.profiling import (
    create_dataset_profile,
)
from backend.etl.quality.reports import (
    create_quality_report,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


def update_job_status(
    job_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """
    Обновляет статус ETL-задачи в базе данных.
    """

    db = SessionLocal()

    try:
        job = db.query(ETLJob).filter(
            ETLJob.id == job_id
        ).first()

        if job:
            job.status = status
            job.error_message = error_message
            db.commit()

    finally:
        db.close()


def get_source_file(version_id: str) -> str:
    """
    Получает путь к исходному файлу из базы данных.
    """

    db = SessionLocal()

    try:
        version = db.query(DatasetVersion).filter(
            DatasetVersion.id == version_id
        ).first()

        if not version:
            raise ValueError(
                f"Версия набора данных {version_id} не найдена"
            )

        source_path = Path(version.source_uri)

        if not source_path.exists():
            raise FileNotFoundError(
                f"Файл не найден: {source_path}"
            )

        return str(source_path)

    finally:
        db.close()


def run_etl(
    dataset_id: str,
    version_id: str,
    job_id: str,
    batch_id: str,
) -> None:
    """
    Запускает полный ETL-процесс.
    """

    data_root = Path(settings.DATA_LAKE_PATH)

    bronze_path = (
        data_root / "bronze" / dataset_id
        / f"batch_id={batch_id}"
    )

    silver_path = (
        data_root / "silver" / dataset_id
        / f"batch_id={batch_id}"
    )

    profile_path = (
        data_root / "gold" / "column_profile"
        / f"{dataset_id}.json"
    )

    quality_path = (
        data_root / "gold" / "data_quality"
        / f"{dataset_id}_{batch_id}.json"
    )

    manifest_path = (
        data_root / "gold" / "etl_runs"
        / f"{dataset_id}_{batch_id}.json"
    )

    spark = None

    try:
        update_job_status(job_id, "running")

        source_path = get_source_file(version_id)

        logger.info("Запуск ETL для %s", dataset_id)

        spark = (
            SparkSession.builder
            .appName("EkoverETL")
            .master("local[*]")
            .getOrCreate()
        )

        # Этап 1. Bronze
        logger.info("Создание слоя Bronze")

        bronze_df = create_bronze_layer(
            spark=spark,
            source_path=source_path,
            output_path=str(bronze_path),
            dataset_id=dataset_id,
            batch_id=batch_id,
        )

        # Этап 2. Silver
        logger.info("Создание слоя Silver")

        silver_df, removed_duplicates = (
            clean_silver_layer(bronze_df)
        )

        save_silver_layer(
            silver_df,
            str(silver_path),
        )

        # Этап 3. Профиль данных
        logger.info("Создание профиля данных")

        profile = create_dataset_profile(
            df=silver_df,
            dataset_id=dataset_id,
            output_path=str(profile_path),
        )

        # Этап 4. Отчёт о качестве
        logger.info("Создание отчёта о качестве")

        quality_report = create_quality_report(
            bronze_df=bronze_df,
            silver_df=silver_df,
            removed_duplicates=removed_duplicates,
            dataset_id=dataset_id,
            batch_id=batch_id,
            output_path=str(quality_path),
        )

        manifest = {
            "dataset_id": dataset_id,
            "version_id": version_id,
            "job_id": job_id,
            "batch_id": batch_id,
            "status": "success",
            "finished_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "profile": str(profile_path),
            "quality_report": str(quality_path),
            "bronze_path": str(bronze_path),
            "silver_path": str(silver_path),
        }

        manifest_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with manifest_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                manifest,
                file,
                ensure_ascii=False,
                indent=4,
            )

        update_job_status(job_id, "success")

        logger.info(
            "ETL успешно завершён. Строк: %s",
            profile["row_count"],
        )

    except Exception as error:
        logger.exception("Ошибка ETL")

        update_job_status(
            job_id,
            "failed",
            str(error),
        )

        raise

    finally:
        if spark:
            spark.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Обработка CSV в Data Lake ЭКОВЕР"
    )

    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-id", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--batch-id", required=True)

    args = parser.parse_args()

    run_etl(
        dataset_id=args.dataset_id,
        version_id=args.version_id,
        job_id=args.job_id,
        batch_id=args.batch_id,
    )


if __name__ == "__main__":
    main()