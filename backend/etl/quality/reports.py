from pyspark.sql import DataFrame
from pyspark.sql.functions import col

from backend.etl.common.publish import utc_now, write_json_atomic
from backend.etl.common.run_context import RunContext
from backend.etl.quality.gate import quality_score


def count_null_cells(df: DataFrame, columns: list[str]) -> int:
    if not columns:
        return 0
    row = (
        df.select(*[col(f"`{name}`").isNull().cast("long") for name in columns])
        .groupBy()
        .sum()
        .first()
    )
    return int(sum(value or 0 for value in row))


def build_quality_report(
    ctx: RunContext,
    status: str,
    results: list[dict],
    bronze_rows: int,
    silver_rows: int,
    quarantined_rows: int,
    null_cells: int,
    gate_reason: str | None = None,
) -> dict:
    failed = [item for item in results if item["status"] == "failed"]
    skipped = [item for item in results if item["status"] == "skipped"]
    evaluated = len(results) - len(skipped)
    return {
        "dataset_id": ctx.dataset_id,
        "version_id": ctx.version_id,
        "batch_id": ctx.batch_id,
        "job_id": ctx.job_id,
        "run_key": ctx.run_key,
        "schema_version": ctx.schema_version,
        "generated_at": utc_now(),
        "quality_status": status,
        "quality_score": quality_score(results),
        "gate_reason": gate_reason,
        "bronze_rows": bronze_rows,
        "silver_rows": silver_rows,
        "removed_duplicates": max(bronze_rows - silver_rows, 0),
        "quarantined_rows": quarantined_rows,
        "null_cells_after_cleaning": null_cells,
        "checks_total": evaluated,
        "checks_passed": evaluated - len(failed),
        "checks_failed": len(failed),
        "checks_skipped": len(skipped),
        "results": results,
    }


def create_quality_report(
    bronze_df: DataFrame,
    silver_df: DataFrame,
    removed_duplicates: int,
    dataset_id: str,
    batch_id: str,
    output_path: str,
) -> dict:
    from pathlib import Path

    silver_rows = silver_df.count()
    report = {
        "dataset_id": dataset_id,
        "batch_id": batch_id,
        "bronze_rows": bronze_df.count(),
        "silver_rows": silver_rows,
        "removed_duplicates": removed_duplicates,
        "null_cells_after_cleaning": count_null_cells(silver_df, silver_df.columns),
        "quality_status": "passed" if silver_rows > 0 else "warning",
    }
    write_json_atomic(Path(output_path), report)
    return report
