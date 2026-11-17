import logging

from pyspark.sql import SparkSession

from backend.etl.common.config import PipelineConfig, load_pipeline_config
from backend.etl.common.exceptions import QualityGateError
from backend.etl.common.logging import log_event
from backend.etl.common.metadata import record_asset, set_job_stage
from backend.etl.common.publish import (
    apply_retention,
    discard_staging,
    is_published,
    publish_layer,
    read_json,
    read_manifest,
    write_json_atomic,
)
from backend.etl.common.run_context import RunContext
from backend.etl.common.spark import managed_spark
from backend.etl.common.stage import run_stage
from backend.etl.jobs.quality_job import quality_report_path
from backend.etl.quality.gate import allows_downstream
from backend.etl.transformations.profiling import compute_profile
from backend.etl.transformations.silver import business_columns

logger = logging.getLogger("etl.gold")

CURATED_DIR = "measurements"


def profile_path(ctx: RunContext):
    return ctx.layer_dir("gold") / "profile.json"

def curated_path(ctx: RunContext):
    return ctx.version_dir("gold") / CURATED_DIR

def run_gold(
    ctx: RunContext,
    config: PipelineConfig | None = None,
    spark: SparkSession | None = None,
    force: bool = False,
) -> dict:
    config = config or load_pipeline_config()

    if not force and is_published(ctx, "gold"):
        log_event(logger, "Gold already published, skipping", ctx)
        return read_manifest(ctx, "gold")

    def action() -> dict:
        set_job_stage(ctx.job_id, "gold")
        report = read_json(quality_report_path(ctx))
        if report is None or report.get("run_key") != ctx.run_key:
            raise QualityGateError("Quality gate для batch не выполнен")
        if not allows_downstream(report["quality_status"], config.allow_warning_downstream):
            raise QualityGateError(
                "Quality gate не пройден, публикация Gold заблокирована",
                {"quality_status": report["quality_status"]},
            )

        staging = ctx.staging_dir("gold")
        with managed_spark(spark, "EkoverGold") as session:
            silver = session.read.parquet(str(ctx.published_dir("silver")))
            if report.get("quarantined_rows", 0) > 0:
                flagged = session.read.parquet(str(ctx.published_dir("quarantine")))
                silver = silver.join(
                    flagged.select("_source_row_number"),
                    on="_source_row_number",
                    how="left_anti",
                )
            try:
                silver.write.mode("errorifexists").parquet(str(staging / CURATED_DIR))
                curated = session.read.parquet(str(staging / CURATED_DIR))
                rows = curated.count()
                profile = compute_profile(
                    curated.select(*business_columns(curated)),
                    ctx.dataset_id, ctx.batch_id, ctx.version_id,
                )
                manifest = publish_layer(
                    ctx,
                    "gold",
                    {
                        "row_count": rows,
                        "columns": business_columns(curated),
                        "quality_status": report["quality_status"],
                        "quality_score": report["quality_score"],
                        "quarantined_rows": report.get("quarantined_rows", 0),
                        "curated_path": str(curated_path(ctx)),
                        "profile_path": str(profile_path(ctx)),
                        "quality_report_path": str(quality_report_path(ctx)),
                    },
                )
            except Exception:
                discard_staging(ctx, "gold")
                raise

        write_json_atomic(profile_path(ctx), profile)
        record_asset(
            ctx.dataset_id, ctx.batch_id, "gold", manifest["curated_path"],
            manifest["row_count"], ctx.schema_version, ctx.run_key,
        )
        for layer in ("bronze", "silver", "gold"):
            apply_retention(ctx, layer)
        return manifest

    return run_stage(ctx, "build_gold", action)
