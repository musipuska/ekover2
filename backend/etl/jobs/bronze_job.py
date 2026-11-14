import logging

from pyspark.sql import SparkSession

from backend.etl.common.logging import log_event
from backend.etl.common.metadata import (
    get_version_info,
    record_asset,
    set_job_stage,
    source_path_for,
)
from backend.etl.common.publish import (
    discard_staging,
    is_published,
    publish_layer,
    read_manifest,
)
from backend.etl.common.run_context import RunContext
from backend.etl.common.source_validation import ensure_utf8_copy, validate_source_file
from backend.etl.common.spark import managed_spark
from backend.etl.common.stage import run_stage, timed
from backend.etl.transformations.bronze import build_bronze_frame

logger = logging.getLogger("etl.bronze")


def run_bronze(ctx: RunContext, spark: SparkSession | None = None, force: bool = False) -> dict:
    if not force and is_published(ctx, "bronze"):
        log_event(logger, "Bronze already published, skipping", ctx)
        return read_manifest(ctx, "bronze")

    def action() -> dict:
        set_job_stage(ctx.job_id, "bronze")
        info = get_version_info(ctx.version_id)
        source = source_path_for(info)
        validation = validate_source_file(source, expected_checksum=info["checksum"])
        metrics: dict = {}
        staging = ctx.staging_dir("bronze")
        read_path = str(source)
        converted = None
        if validation["encoding"] != "UTF-8":
            converted = ctx.layer_dir("bronze") / "_attempts" / f"{ctx.attempt_id}.utf8.csv"
            ensure_utf8_copy(source, validation["python_encoding"], converted)
            read_path = str(converted)

        with managed_spark(spark, "EkoverBronze") as session:
            try:
                with timed(metrics, "write_seconds"):
                    frame = build_bronze_frame(
                        session, ctx, str(source), "UTF-8", read_path=read_path
                    )
                    frame.write.mode("errorifexists").parquet(str(staging))
                written = session.read.parquet(str(staging))
                rows = written.count()
                manifest = publish_layer(
                    ctx,
                    "bronze",
                    {
                        "row_count": rows,
                        "columns": [name for name in written.columns],
                        "source_checksum_sha256": validation["checksum_sha256"],
                        "source_size_bytes": validation["file_size_bytes"],
                        "encoding": validation["encoding"],
                        "metrics": metrics,
                    },
                )
            except Exception:
                discard_staging(ctx, "bronze")
                raise
            finally:
                if converted is not None:
                    converted.unlink(missing_ok=True)

        record_asset(
            ctx.dataset_id, ctx.batch_id, "bronze", manifest["path"],
            manifest["row_count"], ctx.schema_version, ctx.run_key,
        )
        return manifest

    return run_stage(ctx, "build_bronze", action)
