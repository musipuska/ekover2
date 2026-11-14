import os
from contextlib import contextmanager

from pyspark.sql import SparkSession


def get_spark(app_name: str = "EkoverETL") -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
        .master(os.getenv("SPARK_MASTER", "local[*]"))
        .config("spark.ui.enabled", "false")
        .config(
            "spark.sql.shuffle.partitions",
            os.getenv("SPARK_SHUFFLE_PARTITIONS", "8"),
        )
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.ansi.enabled", "false")
    )
    return builder.getOrCreate()


@contextmanager
def managed_spark(spark: SparkSession | None = None, app_name: str = "EkoverETL"):
    created = spark is None
    session = spark or get_spark(app_name)
    try:
        yield session
    finally:
        if created:
            session.stop()
