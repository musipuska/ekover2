import re

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, trim, when
from pyspark.sql.types import StringType


TECHNICAL_COLUMNS = {
    "_dataset_id",
    "_batch_id",
    "_ingested_at",
    "_source_file",
}


def normalize_column_name(name: str) -> str:
    """
    Приводит название столбца к единому формату.
    """

    name = name.strip().lower()
    name = re.sub(r"[^a-zа-яё0-9]+", "_", name)
    name = name.strip("_")

    return name or "column"


def normalize_columns(df: DataFrame) -> DataFrame:
    """
    Нормализует названия столбцов.
    Если названия повторяются, добавляет числовой суффикс.
    """

    used_names = set()
    expressions = []

    for old_name in df.columns:
        if old_name in TECHNICAL_COLUMNS:
            new_name = old_name
        else:
            base_name = normalize_column_name(old_name)
            new_name = base_name
            counter = 2

            while new_name in used_names:
                new_name = f"{base_name}_{counter}"
                counter += 1

        used_names.add(new_name)
        expressions.append(col(f"`{old_name}`").alias(new_name))

    return df.select(*expressions)


def clean_silver_layer(df: DataFrame) -> tuple[DataFrame, int]:
    """
    Очищает данные и удаляет полные дубликаты.

    Возвращает:
    - очищенный DataFrame;
    - количество удалённых строк.
    """

    df = normalize_columns(df)

    for field in df.schema.fields:
        if isinstance(field.dataType, StringType):
            column = col(f"`{field.name}`")

            df = df.withColumn(
                field.name,
                when(
                    trim(column) == "",
                    None
                ).otherwise(trim(column))
            )

    rows_before = df.count()

    df = df.dropDuplicates()

    rows_after = df.count()
    removed_rows = rows_before - rows_after

    return df, removed_rows


def save_silver_layer(
    df: DataFrame,
    output_path: str,
) -> None:
    """
    Сохраняет очищенные данные в Parquet.
    """

    (
        df.write
        .mode("overwrite")
        .parquet(output_path)
    )