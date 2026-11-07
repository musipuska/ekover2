from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    current_timestamp,
    input_file_name,
    lit,
)


def create_bronze_layer(
    spark: SparkSession,
    source_path: str,
    output_path: str,
    dataset_id: str,
    batch_id: str,
) -> DataFrame:
    """
    Читает исходный CSV и создаёт слой Bronze.
    """

    source = Path(source_path)

    if not source.exists():
        raise FileNotFoundError(
            f"Исходный файл не найден: {source_path}"
        )

    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .option("encoding", "UTF-8")
        .csv(str(source))
    )

    if not df.columns:
        raise ValueError("В CSV отсутствуют столбцы")

    df = (
        df
        .withColumn("_dataset_id", lit(dataset_id))
        .withColumn("_batch_id", lit(batch_id))
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_source_file", input_file_name())
    )

    (
        df.write
        .mode("overwrite")
        .parquet(output_path)
    )

    return df