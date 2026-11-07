
import json
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    approx_count_distinct,
    col,
    max as spark_max,
    min as spark_min,
    avg,
)
from pyspark.sql.types import NumericType


def create_dataset_profile(
    df: DataFrame,
    dataset_id: str,
    output_path: str,
    batch_id: str | None = None,
) -> dict:
    """
    Создаёт профиль набора данных и сохраняет его в формате,
    соответствующем схеме DatasetProfile.
    """

    row_count = df.count()
    column_count = len(df.columns)

    # Получаем идентификатор пакета из служебного столбца,
    # если он не был передан явно.
    if batch_id is None:
        if "_batch_id" not in df.columns:
            raise ValueError(
                "Не удалось определить batch_id: "
                "в DataFrame отсутствует столбец _batch_id."
            )

        batch_row = df.select("_batch_id").first()

        if batch_row is None or batch_row["_batch_id"] is None:
            raise ValueError("Не удалось получить batch_id из данных.")

        batch_id = str(batch_row["_batch_id"])

    columns_info = []

    for field in df.schema.fields:
        name = field.name
        column = col(f"`{name}`")

        null_count = (
            df.filter(column.isNull())
            .count()
        )

        null_percent = (
            (null_count / row_count * 100)
            if row_count > 0
            else 0.0
        )

        unique_count = (
            df.select(
                approx_count_distinct(column).alias("unique_count")
            )
            .first()["unique_count"]
        )

        column_info = {
            "name": name,
            "data_type": field.dataType.simpleString(),
            "null_count": int(null_count),
            "null_percent": float(null_percent),
            "unique_count": int(unique_count or 0),
            "min_value": None,
            "max_value": None,
            "average_value": None,
        }

        if isinstance(field.dataType, NumericType):
            stats = df.agg(
                spark_min(column).alias("min_value"),
                spark_max(column).alias("max_value"),
                avg(column).alias("average_value"),
            ).first()

            column_info["min_value"] = stats["min_value"]
            column_info["max_value"] = stats["max_value"]
            column_info["average_value"] = stats["average_value"]

        columns_info.append(column_info)

    profile = {
        "dataset_id": dataset_id,
        "batch_id": batch_id,
        "row_count": row_count,
        "column_count": column_count,
        "columns": columns_info,
    }

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as file:
        json.dump(
            profile,
            file,
            ensure_ascii=False,
            indent=4,
            default=str,
        )

    return profile
