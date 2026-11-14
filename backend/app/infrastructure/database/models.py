from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from backend.app.infrastructure.database.session import Base


class Dataset(Base):
    """Информация о загруженном наборе данных."""

    __tablename__ = "datasets"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(String, default="uploaded")
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class DatasetVersion(Base):
    """Версия исходного файла."""

    __tablename__ = "dataset_versions"

    id = Column(String, primary_key=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    source_uri = Column(String, nullable=False)
    file_format = Column(String, default="csv")
    checksum = Column(String, nullable=False)
    source_filename = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    schema_version = Column(String, nullable=True, default="1.0")
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class ETLJob(Base):
    """Информация о запуске обработки данных."""

    __tablename__ = "etl_jobs"

    id = Column(String, primary_key=True)
    dataset_version_id = Column(
        String,
        ForeignKey("dataset_versions.id"),
        nullable=False
    )
    batch_id = Column(String, nullable=False)
    status = Column(String, default="queued")
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    stage = Column(String, nullable=True)
    run_key = Column(String, nullable=True)
    quality_status = Column(String, nullable=True)
    orchestrator_run_id = Column(String, nullable=True)
    metrics = Column(Text, nullable=True)


class DataQualityResult(Base):
    __tablename__ = "data_quality_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    batch_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=True)
    rule_id = Column(String, nullable=False)
    rule_type = Column(String, nullable=True)
    column_name = Column(String, nullable=True)
    status = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    failed_rows = Column(Integer, nullable=True)
    observed_value = Column(Float, nullable=True)
    expected_value = Column(String, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class DataAsset(Base):
    __tablename__ = "data_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    batch_id = Column(String, nullable=False, index=True)
    layer = Column(String, nullable=False)
    storage_uri = Column(String, nullable=False)
    format = Column(String, default="parquet")
    row_count = Column(BigInteger, nullable=True)
    schema_version = Column(String, nullable=True)
    run_key = Column(String, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )
