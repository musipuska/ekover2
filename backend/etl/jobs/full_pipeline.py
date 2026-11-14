
import argparse
import logging

from pyspark.sql import SparkSession

from backend.analytics.marts import build_marts, validate_marts
from backend.etl.common.config import PipelineConfig, load_pipeline_config
from backend.etl.common.exceptions import ETLError, QualityGateError
from backend.etl.common.logging import log_event, setup_json_logging
from backend.etl.common.metadata import (
    mark_job_started,
    mark_job_finished,
    set_dataset_status,
)
from backend.etl.common.run_context import RunContext
from backend.etl.common.spark import managed_spark
from backend.etl.common.stage import timed
from backend.etl.jobs.bronze_job import run_bronze
from backend.etl.jobs.gold_job import run_gold
from backend.etl.jobs.ingestion import validate_source
from backend.etl.jobs.quality_job import run_quality
from backend.etl.jobs.silver_job import run_silver

logger = logging.getLogger("etl.pipeline")


def run_pipeline(
    dataset_id: str,
    version_id: str,
    job_id: str,
    batch_id: str,
    force: bool = False,
    config: PipelineConfig | None = None,
    spark: SparkSession | None = None,
    orchestrator_run_id: str | None = None,
) -> dict:
    ctx = RunContext.from_ids(
        dataset_id,
        version_id,
        job_id,
        batch_id,
        orchestrator_run_id=orchestrator_run_id,
    )

    config = config or load_pipeline_config()

    metrics: dict = {}
    quality_status = None

    try:
        mark_job_started(
            job_id,
            ctx.run_key,
            orchestrator_run_id,
        )

        # Основные ETL-этапы.
        
        # Основные ETL-этапы.
        with managed_spark(spark, "EkoverETL") as session:

            with timed(metrics, "validate_source"):
                validate_source(ctx, config)

            with timed(metrics, "bronze"):
                bronze = run_bronze(ctx, session, force)

            with timed(metrics, "silver"):
                silver = run_silver(ctx, config, session, force)

            with timed(metrics, "quality"):
                report = run_quality(
                    ctx,
                    config,
                    session,
                    force,
                )

            quality_status = report["quality_status"]

            with timed(metrics, "gold"):
                gold = run_gold(
                    ctx,
                    config,
                    session,
                    force,
                )

        # На этом этапе Spark уже завершил работу,
        # а Gold должен быть опубликован.
        # Аналитические витрины строятся на основе Gold.

        with timed(metrics, "analytics_marts"):
            marts = build_marts(
                dataset_id=dataset_id,
                batch_id=batch_id,
            )

            validation = validate_marts(
                dataset_id=dataset_id,
                batch_id=batch_id,
            )

        metrics.update(
            rows_bronze=bronze["row_count"],
            rows_silver=silver["row_count"],
            rows_gold=gold["row_count"],
            analytics_marts=marts["marts"],
            analytics_validation=validation,
        )

        mark_job_finished(
            job_id,
            "success",
            None,
            quality_status,
            metrics,
        )

        set_dataset_status(dataset_id, "success")

        log_event(
            logger,
            "Pipeline finished",
            ctx,
            metrics=metrics,
        )

        return {
            "status": "success",
            "quality_status": quality_status,
            "metrics": metrics,
        }

    except QualityGateError as error:
        mark_job_finished(
            job_id,
            "failed",
            f"{error.code}: {error.message}",
            "failed",
            metrics,
        )

        set_dataset_status(dataset_id, "failed")

        log_event(
            logger,
            "Pipeline blocked by quality gate",
            ctx,
            level=logging.ERROR,
            error=error.to_dict(),
        )

        raise

    except Exception as error:
        message = (
            f"{error.code}: {error.message}"
            if isinstance(error, ETLError)
            else str(error)
        )

        mark_job_finished(
            job_id,
            "failed",
            message,
            quality_status,
            metrics,
        )

        set_dataset_status(dataset_id, "failed")

        log_event(
            logger,
            "Pipeline failed",
            ctx,
            level=logging.ERROR,
            error=message,
        )

        raise


def main() -> None:
    setup_json_logging()

    parser = argparse.ArgumentParser(
        description="Полный ETL-пайплайн ЭКОВЕР"
    )

    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-id", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    run_pipeline(
        dataset_id=args.dataset_id,
        version_id=args.version_id,
        job_id=args.job_id,
        batch_id=args.batch_id,
        force=args.force,
    )


if __name__ == "__main__":
    main()
