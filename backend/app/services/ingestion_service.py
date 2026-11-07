import csv
import hashlib
import io
import logging
import re
import uuid

from pathlib import Path
from sqlalchemy.orm import Session

from backend.app.core.exceptions import InvalidFileError
from backend.app.infrastructure.database.models import (
    Dataset,
    DatasetVersion,
    ETLJob
)
from backend.app.infrastructure.storage.base import StorageInterface
from backend.app.repositories import dataset_repository
from backend.app.repositories import job_repository


logger = logging.getLogger(__name__)


def validate_csv(filename: str, content: bytes) -> None:
    """Проверяет формат, размер и читаемость CSV-файла."""

    if Path(filename).suffix.lower() != ".csv":
        raise InvalidFileError("Можно загружать только CSV-файлы.")

    if not content:
        raise InvalidFileError("Файл пустой.")

    if len(content) > 50 * 1024 * 1024:
        raise InvalidFileError("Размер файла превышает 50 МБ.")

    try:
        decoded = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(decoded))

        header = next(reader, None)

        if not header or not any(cell.strip() for cell in header):
            raise InvalidFileError("В CSV отсутствует заголовок.")

        if len(set(header)) != len(header):
            raise InvalidFileError(
                "В CSV обнаружены повторяющиеся названия колонок."
            )

        if not any(reader):
            raise InvalidFileError("В CSV отсутствуют строки с данными.")

    except UnicodeDecodeError as error:
        raise InvalidFileError(
            "Не удалось прочитать файл. Поддерживается UTF-8."
        ) from error
    except csv.Error as error:
        raise InvalidFileError("Некорректный CSV-файл.") from error


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
    """Сохраняет исходный CSV и регистрирует задачу обработки."""

    validate_csv(filename, content)

    dataset_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    batch_id = str(uuid.uuid4())

    checksum = hashlib.sha256(content).hexdigest()

    temporary_path = None
    saved_uri = None

    try:
        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix=".csv",
            delete=False
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

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
            checksum=checksum
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

    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)