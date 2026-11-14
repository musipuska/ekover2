import csv
import hashlib
import io
from pathlib import Path

from backend.etl.common.exceptions import SchemaError, ValidationError

ENCODINGS = (
    ("utf-8-sig", "UTF-8"),
    ("cp1251", "windows-1251"),
)


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def detect_encoding(sample: bytes) -> tuple[str, str]:
    for python_name, spark_name in ENCODINGS:
        try:
            sample.decode(python_name)
            return python_name, spark_name
        except UnicodeDecodeError:
            continue
    raise ValidationError("Не удалось определить кодировку файла (UTF-8 / windows-1251)")


def _decode_sample(raw: bytes, python_name: str, truncated: bool) -> str:
    if truncated:
        raw = raw[: raw.rfind(b"\n") + 1] or raw
    return raw.decode(python_name, errors="replace")


def validate_source_file(
    path: Path,
    expected_checksum: str | None = None,
    required_columns: list[str] | None = None,
    sample_bytes: int = 1024 * 1024,
) -> dict:
    if not path.is_file():
        raise ValidationError(f"Файл не найден: {path}", {"path": str(path)})

    size = path.stat().st_size
    if size == 0:
        raise ValidationError("Файл пустой", {"path": str(path)})

    checksum = file_sha256(path)
    if expected_checksum and checksum != expected_checksum:
        raise ValidationError(
            "Контрольная сумма файла не совпадает с зарегистрированной",
            {"expected": expected_checksum, "actual": checksum},
        )

    with path.open("rb") as file:
        raw = file.read(sample_bytes)

    python_name, spark_name = detect_encoding(raw[:-3] if len(raw) > 3 and size > sample_bytes else raw)
    text = _decode_sample(raw, python_name, truncated=size > sample_bytes)

    try:
        rows = csv.reader(io.StringIO(text))
        header = next(rows, None)
        first_row = next(rows, None)
    except csv.Error as error:
        raise SchemaError(f"Некорректный CSV: {error}") from error

    if not header or not any(cell.strip() for cell in header):
        raise SchemaError("В CSV отсутствует заголовок")
    if first_row is None:
        raise ValidationError("В CSV отсутствуют строки с данными")

    empty_names = [index for index, cell in enumerate(header) if not cell.strip()]
    if empty_names:
        raise SchemaError("В заголовке есть пустые названия столбцов", {"positions": empty_names})

    normalized = [cell.strip().lower() for cell in header]
    if required_columns:
        missing = [name for name in required_columns if name.lower() not in normalized]
        if missing:
            raise SchemaError("Отсутствуют обязательные столбцы", {"missing": missing})

    duplicates = sorted({name for name in header if header.count(name) > 1})

    return {
        "checksum_sha256": checksum,
        "file_size_bytes": size,
        "encoding": spark_name,
        "python_encoding": python_name,
        "columns": [cell.strip() for cell in header],
        "duplicate_columns": duplicates,
    }


def ensure_utf8_copy(source: Path, python_encoding: str, target: Path, chunk_chars: int = 1024 * 1024) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("r", encoding=python_encoding, newline="") as reader, target.open(
        "w", encoding="utf-8", newline=""
    ) as writer:
        while chunk := reader.read(chunk_chars):
            writer.write(chunk)
    return target
