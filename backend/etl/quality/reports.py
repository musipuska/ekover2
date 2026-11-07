import json
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql.functions import col


def create_quality_report(
    bronze_df: DataFrame,
    silver_df: DataFrame,
    removed_duplicates: int,
    dataset_id: str,
    batch_id: str,
    output_path: str,
) -> dict:
    """
    Формирует отчёт о качестве обработанных данных.
    """

    bronze_rows = bronze_df.count()
    silver_rows = silver_df.count()

    null_expressions = [
        col(f"`{name}`").isNull().cast("long")
        for name in silver_df.columns
    ]

    if null_expressions:
        null_row = silver_df.select(
            *null_expressions
        ).groupBy().sum().first()

        null_count = sum(
            value or 0 for value in null_row
        )
    else:
        null_count = 0

    report = {
        "dataset_id": dataset_id,
        "batch_id": batch_id,
        "bronze_rows": bronze_rows,
        "silver_rows": silver_rows,
        "removed_duplicates": removed_duplicates,
        "null_cells_after_cleaning": null_count,
        "quality_status": (
            "success" if silver_rows > 0 else "warning"
        ),
    }

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=4,
        )

    return report