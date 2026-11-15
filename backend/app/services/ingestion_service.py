import csv
import hashlib
import io
import logging
import re
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.exceptions import InvalidFileError
from backend.app.infrastructure.database.models import Dataset, DatasetVersion, ETLJob
from backend.app.infrastructure.storage.base import StorageInterface
from backend.app.repositories import dataset_repository, job_repository

logger = logging.getLogger(__name__)


CHUNK_SIZE = 1024 * 1024


def validate_csv_file(filename: str, path: Path) -> None:
    """Проверяет формат и читаемость CSV построчно, не загружая файл в память."""

    if Path(filename).suffix.lower() != ".csv":
        raise InvalidFileError("Можно загружать только CSV-файлы.")

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file)
            header = next(reader, None)

            if not header or not any(cell.strip() for cell in header):
                raise InvalidFileError("В CSV отсутствует заголовок.")

            if len(set(header)) != len(header):
                raise InvalidFileError(
                    "В CSV обнаружены повторяющиеся названия колонок."
                )

            if not any(True for _ in reader):
                raise InvalidFileError("В CSV отсутствуют строки с данными.")
    except UnicodeDecodeError as error:
        raise InvalidFileError(
            "Не удалось прочитать файл. Поддерживается UTF-8."
        ) from error
    except csv.Error as error:
        raise InvalidFileError("Некорректный CSV-файл.") from error


def validate_csv(filename: str, content: bytes) -> None:
    """Проверка CSV из байтов (для небольших файлов и тестов)."""

    if not content:
        raise InvalidFileError("Файл пустой.")
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise InvalidFileError(_size_message())

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
        handle.write(content)
        path = Path(handle.name)
    try:
        validate_csv_file(filename, path)
    finally:
        path.unlink(missing_ok=True)


def _size_message() -> str:
    return f"Размер файла превышает {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} МБ."


def receive_stream(stream: BinaryIO) -> tuple[Path, str, int]:
    """Копирует поток во временный файл, считая SHA-256 и размер на лету.

    При превышении MAX_UPLOAD_SIZE или ошибке временный файл удаляется.
    """

    import tempfile

    digest = hashlib.sha256()
    size = 0
    handle = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    path = Path(handle.name)
    try:
        with handle:
            while chunk := stream.read(CHUNK_SIZE):
                size += len(chunk)
                if size > settings.MAX_UPLOAD_SIZE:
                    raise InvalidFileError(_size_message())
                digest.update(chunk)
                handle.write(chunk)
        if size == 0:
            raise InvalidFileError("Файл пустой.")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path, digest.hexdigest(), size


def safe_filename(filename: str) -> str:
    """Оставляет безопасную часть имени файла."""

    name = Path(filename).name
    name = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9_.-]", "_", name)

    return name[:150] or "dataset.csv"


def upload_dataset(
    db: Session,
    storage: StorageInterface,
    filename: str,
    content: bytes
) -> dict:
    """Совместимая обёртка: загрузка из байтов."""

    return upload_stream(db, storage, filename, io.BytesIO(content))


def upload_stream(
    db: Session,
    storage: StorageInterface,
    filename: str,
    stream: BinaryIO,
) -> dict:
    """Потоково принимает CSV, сохраняет его и регистрирует задачу обработки."""

    temporary_path, checksum, size = receive_stream(stream)
    try:
        validate_csv_file(filename, temporary_path)
        return _register_upload(db, storage, filename, temporary_path, checksum, size)
    finally:
        temporary_path.unlink(missing_ok=True)


def _register_upload(
    db: Session,
    storage: StorageInterface,
    filename: str,
    temporary_path: Path,
    checksum: str,
    size: int,
) -> dict:

    dataset_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    batch_id = str(uuid.uuid4())

    saved_uri = None

    try:
        destination = (
            f"raw/{dataset_id}/{version_id}_"
            f"{safe_filename(filename)}"
        )

        saved_uri = storage.save(temporary_path, destination)

        dataset = Dataset(
            id=dataset_id,
            name=Path(filename).stem,
            status="uploaded"
        )

        version = DatasetVersion(
            id=version_id,
            dataset_id=dataset_id,
            source_uri=saved_uri,
            file_format="csv",
            checksum=checksum,
            source_filename=safe_filename(filename),
            file_size_bytes=size,
            schema_version="1.0"
        )

        job = ETLJob(
            id=job_id,
            dataset_version_id=version_id,
            batch_id=batch_id,
            status="queued"
        )

        dataset_repository.create_dataset(db, dataset)
        dataset_repository.create_version(db, version)
        job_repository.create_job(db, job)

        db.commit()

        logger.info(
            "Dataset uploaded: dataset_id=%s job_id=%s",
            dataset_id,
            job_id
        )

        return {
            "dataset_id": dataset_id,
            "version_id": version_id,
            "job_id": job_id,
            "batch_id": batch_id,
            "filename": filename,
            "status": "queued",
            "message": "Файл сохранён. Задача обработки создана."
        }

    except Exception:
        db.rollback()

        if saved_uri:
            try:
                Path(saved_uri).unlink(missing_ok=True)
            except OSError:
                logger.exception("Не удалось удалить файл после ошибки.")

        raise
