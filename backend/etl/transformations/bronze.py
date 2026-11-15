from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql.functions import (
    coalesce,
    col,
    concat_ws,
    count,
    create_map,
    current_timestamp,
    lit,
    monotonically_increasing_id,
    row_number,
    sha2,
    spark_partition_id,
)
from pyspark.sql.types import StructType

from backend.etl.common.run_context import RunContext

TECHNICAL_COLUMNS = (
    "_dataset_id",
    "_version_id",
    "_batch_id",
    "_ingested_at",
    "_source_file",
    "_source_row_number",
    "_record_hash",
)

NULL_MARKER = "␀"


def read_source_csv(
    spark: SparkSession,
    source_path: str,
    encoding: str = "UTF-8",
    schema: StructType | None = None,
) -> DataFrame:
    if not Path(source_path).exists():
        raise FileNotFoundError(f"Исходный файл не найден: {source_path}")

    reader = (
        spark.read.option("header", True)
        .option("encoding", encoding)
        .option("multiLine", True)
        .option("escape", '"')
    )
    reader = reader.schema(schema) if schema is not None else reader.option("inferSchema", True)
    df = reader.csv(str(source_path))

    if not df.columns:
        raise ValueError("В CSV отсутствуют столбцы")
    return df


def add_row_numbers(spark: SparkSession, df: DataFrame) -> DataFrame:
    """Сквозной номер строки 1..N в порядке чтения файла без RDD и без одного раздела.

    Номера внутри раздела считаются оконной функцией, смещения разделов —
    из небольшой таблицы количеств строк по разделам.
    """
    tagged = df.withColumn("__pid", spark_partition_id()).withColumn(
        "__mid", monotonically_increasing_id()
    )
    counts = {
        row["__pid"]: row["cnt"]
        for row in tagged.groupBy("__pid").agg(count(lit(1)).alias("cnt")).collect()
    }
    offsets: dict[int, int] = {}
    running = 0
    for pid in sorted(counts):
        offsets[pid] = running
        running += counts[pid]

    offset_map = create_map(*[x for pid, off in offsets.items() for x in (lit(pid), lit(off))])
    window = Window.partitionBy("__pid").orderBy("__mid")
    numbered = tagged.withColumn(
        "_source_row_number",
        (row_number().over(window) + offset_map[col("__pid")]).cast("long"),
    ).drop("__pid", "__mid")
    ordered = ["_source_row_number", *[name for name in df.columns]]
    return numbered.select(*[col(f"`{name}`") for name in ordered])


def add_technical_columns(
    spark: SparkSession,
    df: DataFrame,
    ctx: RunContext,
    source_file: str,
) -> DataFrame:
    source_columns = list(df.columns)
    hash_input = [
        coalesce(col(f"`{name}`").cast("string"), lit(NULL_MARKER))
        for name in source_columns
    ]
    df = add_row_numbers(spark, df)
    return (
        df.withColumn("_record_hash", sha2(concat_ws("␟", *hash_input), 256))
        .withColumn("_dataset_id", lit(ctx.dataset_id))
        .withColumn("_version_id", lit(ctx.version_id))
        .withColumn("_batch_id", lit(ctx.batch_id))
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_source_file", lit(Path(source_file).name))
    )


def build_bronze_frame(
    spark: SparkSession,
    ctx: RunContext,
    source_path: str,
    encoding: str = "UTF-8",
    schema: StructType | None = None,
    read_path: str | None = None,
) -> DataFrame:
    raw = read_source_csv(spark, read_path or source_path, encoding, schema)
    return add_technical_columns(spark, raw, ctx, source_path)


def create_bronze_layer(
    spark: SparkSession,
    source_path: str,
    output_path: str,
    dataset_id: str,
    batch_id: str,
    version_id: str = "unknown",
    encoding: str = "UTF-8",
) -> DataFrame:
    ctx = RunContext(
        dataset_id=dataset_id,
        version_id=version_id,
        batch_id=batch_id,
        job_id="adhoc",
    )
    frame = build_bronze_frame(spark, ctx, source_path, encoding)
    frame.write.mode("errorifexists").parquet(output_path)
    return frame
