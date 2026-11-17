import re

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.functions import col, row_number, to_timestamp, trim, when
from pyspark.sql.types import StringType, TimestampType
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

def build_measured_at(df: DataFrame) -> DataFrame:
    if "date" not in df.columns or "time" not in df.columns:
        return df

    date_value = F.trim(F.col("date").cast("string"))

    # Распознаём дату в нескольких форматах
    parsed_date = F.coalesce(
        F.try_to_timestamp(date_value, F.lit("MM-dd-yy")),
        F.try_to_timestamp(date_value, F.lit("yyyy-MM-dd")),
        F.try_to_timestamp(date_value, F.lit("dd/MM/yyyy")),
    )

    # Если Spark уже преобразовал время в timestamp,
    # извлекаем только часы, минуты и секунды
    if isinstance(df.schema["time"].dataType, TimestampType):
        time_value = F.date_format(F.col("time"), "HH:mm:ss")
    else:
        raw_time = F.trim(F.col("time").cast("string"))
        time_datetime = F.concat(F.lit("1970-01-01 "), raw_time)

        parsed_time = F.coalesce(
            F.try_to_timestamp(time_datetime, F.lit("yyyy-MM-dd H:mm:ss")),
            F.try_to_timestamp(time_datetime, F.lit("yyyy-MM-dd HH:mm:ss")),
            F.try_to_timestamp(time_datetime, F.lit("yyyy-MM-dd H:mm")),
            F.try_to_timestamp(time_datetime, F.lit("yyyy-MM-dd HH:mm")),
        )

        time_value = F.date_format(parsed_time, "HH:mm:ss")

    # Формируем полноценную дату и время
    datetime_value = F.concat(
        F.date_format(parsed_date, "yyyy-MM-dd"),
        F.lit(" "),
        time_value,
    )

    measured_at = F.when(
        parsed_date.isNotNull() & time_value.isNotNull(),
        F.try_to_timestamp(
            datetime_value,
            F.lit("yyyy-MM-dd HH:mm:ss"),
        ),
    )

    return (
        df
        .withColumn("time", time_value)
        .withColumn("measured_at", measured_at)
    )

def standardize_timestamps(df: DataFrame, columns: list[str]) -> DataFrame:
    for name in columns:
        if name in df.columns:
            df = df.withColumn(name, to_timestamp(col(f"`{name}`")))
    return df


def resolve_strategy(strategy: str, business_key: list[str] | None) -> str:
    if strategy == "auto":
        return "business_key" if business_key else "full_row"
    if strategy == "business_key" and not business_key:
        raise ValueError("dedup_strategy=business_key требует business_key")
    return strategy


def deduplicate(
    df: DataFrame,
    business_key: list[str] | None = None,
    strategy: str = "auto",
) -> DataFrame:
    strategy = resolve_strategy(strategy, business_key)
    if strategy == "none":
        return df
    if strategy == "record_hash" and "_record_hash" in df.columns:
        return df.dropDuplicates(["_record_hash"])
    key = [name for name in (business_key or []) if name in df.columns]
    if strategy == "business_key" and key:
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
    dedup_strategy: str = "auto",
) -> tuple[DataFrame, int]:
    df = normalize_columns(df)
    df = standardize_strings(df)
    df = build_measured_at(df)
    df = standardize_timestamps(df, timestamp_columns or [])
    rows_before = df.count()
    df = deduplicate(df, business_key, dedup_strategy)
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
