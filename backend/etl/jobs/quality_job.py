import logging

from pyspark.sql import SparkSession

from backend.etl.common.config import PipelineConfig, RuleSpec, load_pipeline_config
from backend.etl.common.exceptions import QualityGateError, ValidationError
from backend.etl.common.logging import log_event
from backend.etl.common.metadata import (
    previous_row_count,
    record_asset,
    record_quality_results,
    set_job_stage,
)
from backend.etl.common.publish import (
    discard_staging,
    is_published,
    publish_layer,
    read_json,
    write_blocked_manifest,
    write_json_atomic,
)
from backend.etl.common.run_context import RunContext
from backend.etl.common.spark import managed_spark
from backend.etl.common.stage import run_stage
from backend.etl.quality.gate import FAILED, allows_downstream, evaluate_gate
from backend.etl.quality.reports import build_quality_report, count_null_cells
from backend.etl.quality.rules import evaluate_rules
from backend.etl.transformations.silver import business_columns, normalize_column_name

logger = logging.getLogger("etl.quality")


def quality_report_path(ctx: RunContext):
    return ctx.layer_dir("gold") / "quality_report.json"


def compose_rules(config: PipelineConfig) -> list[RuleSpec]:
    specs = list(config.rules)
    names = {spec.name for spec in specs}
    if config.required_columns and "required_columns" not in names:
        specs.append(
            RuleSpec(
                name="required_columns",
                rule="required_columns",
                severity="critical",
                columns=[normalize_column_name(name) for name in config.required_columns],
            )
        )
    if config.business_key and "business_key_unique" not in names:
        specs.append(
            RuleSpec(
                name="business_key_unique",
                rule="unique",
                severity="critical",
                columns=[normalize_column_name(name) for name in config.business_key],
            )
        )
    return specs


def run_quality(
    ctx: RunContext,
    config: PipelineConfig | None = None,
    spark: SparkSession | None = None,
    force: bool = False,
) -> dict:
    config = config or load_pipeline_config()

    if not force and is_published(ctx, "gold"):
        existing = read_json(quality_report_path(ctx))
        if existing and existing.get("run_key") == ctx.run_key:
            log_event(logger, "Quality already evaluated for published gold", ctx)
            return existing

    def action() -> dict:
        set_job_stage(ctx.job_id, "quality")
        if not is_published(ctx, "silver"):
            raise ValidationError(
                "Silver не опубликован для этого batch",
                {"batch_id": ctx.batch_id},
            )

        with managed_spark(spark, "EkoverQuality") as session:
            silver = session.read.parquet(str(ctx.published_dir("silver")))
            bronze_rows = read_json(ctx.manifest_path("bronze"))["row_count"]
            previous = previous_row_count(ctx.dataset_id, ctx.batch_id)

            results, quarantine_condition, silver_rows = evaluate_rules(
                silver, compose_rules(config), previous
            )
            status = evaluate_gate(results)

            quarantined = 0
            if quarantine_condition is not None:
                flagged = silver.filter(quarantine_condition)
                staging = ctx.staging_dir("quarantine")
                try:
                    flagged.write.mode("errorifexists").parquet(str(staging))
                    quarantined = session.read.parquet(str(staging)).count()
                    if quarantined:
                        manifest = publish_layer(
                            ctx, "quarantine", {"row_count": quarantined}
                        )
                        record_asset(
                            ctx.dataset_id, ctx.batch_id, "quarantine",
                            manifest["path"], quarantined,
                            ctx.schema_version, ctx.run_key,
                        )
                    else:
                        discard_staging(ctx, "quarantine")
                except Exception:
                    discard_staging(ctx, "quarantine")
                    raise

            null_cells = count_null_cells(silver, business_columns(silver))

        failed_critical = [
            item["rule"] for item in results
            if item["status"] == "failed" and item["severity"] == "critical"
        ]
        reason = (
            f"Нарушены критические правила: {', '.join(failed_critical)}"
            if failed_critical else None
        )
        report = build_quality_report(
            ctx, status, results, bronze_rows, silver_rows,
            quarantined, null_cells, reason,
        )
        write_json_atomic(quality_report_path(ctx), report)
        record_quality_results(ctx.dataset_id, ctx.batch_id, ctx.job_id, results)

        if not allows_downstream(status, config.allow_warning_downstream):
            write_blocked_manifest(
                ctx, "gold",
                reason or "Quality gate не пройден",
                {"quality_status": status or FAILED},
            )
            raise QualityGateError(
                reason or "Quality gate не пройден",
                {"quality_status": status, "failed_rules": failed_critical},
            )
        return report

    return run_stage(ctx, "quality_gate", action)
