from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import NumericType

from backend.etl.common.publish import write_json_atomic


def compute_profile(df: DataFrame, dataset_id: str, batch_id: str, version_id: str | None = None) -> dict:
    fields = df.schema.fields
    expressions = [F.count(F.lit(1)).alias("__rows__")]

    for index, field in enumerate(fields):
        column = F.col(f"`{field.name}`")
        expressions.append(F.sum(F.when(column.isNull(), 1).otherwise(0)).alias(f"n{index}"))
        expressions.append(F.approx_count_distinct(column).alias(f"u{index}"))
        if isinstance(field.dataType, NumericType):
            expressions.append(F.min(column).alias(f"min{index}"))
            expressions.append(F.max(column).alias(f"max{index}"))
            expressions.append(F.avg(column).alias(f"avg{index}"))

    stats = df.agg(*expressions).first().asDict()
    row_count = int(stats["__rows__"] or 0)

    columns = []
    for index, field in enumerate(fields):
        null_count = int(stats[f"n{index}"] or 0)
        info = {
            "name": field.name,
            "data_type": field.dataType.simpleString(),
            "null_count": null_count,
            "null_percent": (null_count / row_count * 100) if row_count else 0.0,
            "unique_count": int(stats[f"u{index}"] or 0),
            "min_value": None,
            "max_value": None,
            "average_value": None,
        }
        if isinstance(field.dataType, NumericType):
            info["min_value"] = stats[f"min{index}"]
            info["max_value"] = stats[f"max{index}"]
            info["average_value"] = stats[f"avg{index}"]
        columns.append(info)

    return {
        "dataset_id": dataset_id,
        "version_id": version_id,
        "batch_id": batch_id,
        "row_count": row_count,
        "column_count": len(fields),
        "columns": columns,
    }


def create_dataset_profile(
    df: DataFrame,
    dataset_id: str,
    output_path: str,
    batch_id: str | None = None,
) -> dict:
    if batch_id is None:
        if "_batch_id" not in df.columns:
            raise ValueError("Не удалось определить batch_id: нет столбца _batch_id.")
        row = df.select("_batch_id").first()
        if row is None or row["_batch_id"] is None:
            raise ValueError("Не удалось получить batch_id из данных.")
        batch_id = str(row["_batch_id"])

    profile = compute_profile(df, dataset_id, batch_id)
    write_json_atomic(Path(output_path), profile)
    return profile
