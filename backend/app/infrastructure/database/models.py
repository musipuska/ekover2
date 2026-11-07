from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Text

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