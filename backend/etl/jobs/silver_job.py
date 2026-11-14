import logging

from pyspark.sql import SparkSession

from backend.etl.common.config import PipelineConfig, load_pipeline_config
from backend.etl.common.exceptions import ValidationError
from backend.etl.common.logging import log_event
from backend.etl.common.metadata import record_asset, set_job_stage
from backend.etl.common.publish import (
    discard_staging,
    is_published,
    publish_layer,
    read_manifest,
)
from backend.etl.common.run_context import RunContext
from backend.etl.common.spark import managed_spark
from backend.etl.common.stage import run_stage, timed
from backend.etl.transformations.silver import clean_silver_frame, normalize_column_name

logger = logging.getLogger("etl.silver")


def run_silver(
    ctx: RunContext,
    config: PipelineConfig | None = None,
    spark: SparkSession | None = None,
    force: bool = False,
) -> dict:
    config = config or load_pipeline_config()

    if not force and is_published(ctx, "silver"):
        log_event(logger, "Silver already published, skipping", ctx)
        return read_manifest(ctx, "silver")

    def action() -> dict:
        set_job_stage(ctx.job_id, "silver")
        if not is_published(ctx, "bronze"):
            raise ValidationError(
                "Bronze не опубликован для этого batch",
                {"batch_id": ctx.batch_id},
            )
        metrics: dict = {}
        staging = ctx.staging_dir("silver")
        key = [normalize_column_name(name) for name in config.business_key]
        timestamps = [normalize_column_name(name) for name in config.timestamp_columns]

        with managed_spark(spark, "EkoverSilver") as session:
            bronze = session.read.parquet(str(ctx.published_dir("bronze")))
            try:
                with timed(metrics, "transform_seconds"):
                    cleaned, rows_in = clean_silver_frame(bronze, key, timestamps)
                    cleaned.write.mode("errorifexists").parquet(str(staging))
                written = session.read.parquet(str(staging))
                rows_out = written.count()
                manifest = publish_layer(
                    ctx,
                    "silver",
                    {
                        "row_count": rows_out,
                        "rows_in": rows_in,
                        "removed_duplicates": rows_in - rows_out,
                        "dedup_strategy": "business_key" if key else "full_row",
                        "business_key": key,
                        "columns": written.columns,
                        "metrics": metrics,
                    },
                )
            except Exception:
                discard_staging(ctx, "silver")
                raise

        record_asset(
            ctx.dataset_id, ctx.batch_id, "silver", manifest["path"],
            manifest["row_count"], ctx.schema_version, ctx.run_key,
        )
        return manifest

    return run_stage(ctx, "build_silver", action)
