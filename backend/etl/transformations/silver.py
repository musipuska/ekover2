import re

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, row_number, to_timestamp, trim, when
from pyspark.sql.types import StringType
from pyspark.sql.window import Window

from backend.etl.transformations.bronze import TECHNICAL_COLUMNS

TECHNICAL_SET = set(TECHNICAL_COLUMNS)


def normalize_column_name(name: str) -> str:
    name = name.strip().lstrip("﻿").lower()
    name = re.sub(r"[^a-zа-яё0-9]+", "_", name)
    name = name.strip("_")
    return name or "column"


def normalize_columns(df: DataFrame) -> DataFrame:
    used: set[str] = set()
    expressions = []

    for old_name in df.columns:
        if old_name in TECHNICAL_SET:
            new_name = old_name
        else:
            base = normalize_column_name(old_name)
            new_name = base
            counter = 2
            while new_name in used or new_name in TECHNICAL_SET:
                new_name = f"{base}_{counter}"
                counter += 1
        used.add(new_name)
        expressions.append(col(f"`{old_name}`").alias(new_name))

    return df.select(*expressions)


def business_columns(df: DataFrame) -> list[str]:
    return [name for name in df.columns if name not in TECHNICAL_SET]


def standardize_strings(df: DataFrame) -> DataFrame:
    for field in df.schema.fields:
        if field.name in TECHNICAL_SET or not isinstance(field.dataType, StringType):
            continue
        column = col(f"`{field.name}`")
        df = df.withColumn(
            field.name,
            when(trim(column) == "", None).otherwise(trim(column)),
        )
    return df


def standardize_timestamps(df: DataFrame, columns: list[str]) -> DataFrame:
    for name in columns:
        if name in df.columns:
            df = df.withColumn(name, to_timestamp(col(f"`{name}`")))
    return df


def deduplicate(df: DataFrame, business_key: list[str] | None = None) -> DataFrame:
    key = [name for name in (business_key or []) if name in df.columns]
    if key:
        order = col("_source_row_number").desc() if "_source_row_number" in df.columns else col(key[0])
        window = Window.partitionBy(*[col(f"`{name}`") for name in key]).orderBy(order)
        return (
            df.withColumn("_rn", row_number().over(window))
            .filter(col("_rn") == 1)
            .drop("_rn")
        )
    subset = business_columns(df)
    return df.dropDuplicates(subset) if subset else df.dropDuplicates()


def clean_silver_frame(
    df: DataFrame,
    business_key: list[str] | None = None,
    timestamp_columns: list[str] | None = None,
) -> tuple[DataFrame, int]:
    df = normalize_columns(df)
    df = standardize_strings(df)
    df = standardize_timestamps(df, timestamp_columns or [])
    rows_before = df.count()
    df = deduplicate(df, business_key)
    return df, rows_before


def clean_silver_layer(
    df: DataFrame,
    business_key: list[str] | None = None,
    timestamp_columns: list[str] | None = None,
) -> tuple[DataFrame, int]:
    cleaned, rows_before = clean_silver_frame(df, business_key, timestamp_columns)
    return cleaned, rows_before - cleaned.count()


def save_silver_layer(df: DataFrame, output_path: str) -> None:
    df.write.mode("errorifexists").parquet(output_path)
