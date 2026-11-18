import re
from datetime import date, datetime, time, timedelta, timezone

from backend.app.api.envelope import ApiError

_UNSAFE_ID = re.compile(r"[/\\*?\[\]]")
_ABS_PATH = re.compile(r"(?:[A-Za-z]:\\|/)(?:[\w.\- ]+[/\\])+[\w.\- ]*")
MAX_ERROR_LENGTH = 300


def safe_id(value: str | None, field: str) -> str | None:
    """Идентификаторы попадают в пути data lake, поэтому отсекаем всё, что может выйти из партиции."""
    if value is None or value == "":
        return None
    if _UNSAFE_ID.search(value) or value in {".", ".."} or len(value) > 128:
        raise ApiError("INVALID_PARAMETER", f"Недопустимое значение параметра {field}", 422, {"field": field})
    return value


def parse_day(value: str | None, field: str) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ApiError(
            "INVALID_DATE", f"{field}: ожидается дата в формате YYYY-MM-DD", 422, {"field": field, "value": value}
        ) from error


def date_range(date_from: str | None, date_to: str | None) -> tuple[date | None, date | None]:
    start, end = parse_day(date_from, "date_from"), parse_day(date_to, "date_to")
    if start and end and start > end:
        raise ApiError("INVALID_RANGE", "date_from не может быть позже date_to", 422)
    return start, end


def utc_bounds(start: date | None, end: date | None) -> tuple[datetime | None, datetime | None]:
    """Границы для сравнения с naive-UTC datetime из БД: [start, end + 1 день)."""
    low = datetime.combine(start, time.min) if start else None
    high = datetime.combine(end + timedelta(days=1), time.min) if end else None
    return low, high


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def in_day_range(stamp: str | None, start: date | None, end: date | None) -> bool:
    """Проверка ISO-строки (published_at и т. п.) на попадание в диапазон дат."""
    if not (start or end):
        return True
    if not stamp:
        return False
    try:
        day = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc).date()
    except ValueError:
        return False
    return (start is None or day >= start) and (end is None or day <= end)


def sanitize_error(message: str | None) -> str | None:
    """Скрывает абсолютные пути файловой системы и ограничивает длину сообщения."""
    if not message:
        return message
    cleaned = _ABS_PATH.sub("<path>", message)
    if len(cleaned) > MAX_ERROR_LENGTH:
        cleaned = cleaned[: MAX_ERROR_LENGTH - 1] + "…"
    return cleaned


def error_type(message: str | None) -> str:
    """ETL-ошибки имеют вид `CODE: текст` (см. full_pipeline); остальное — UNKNOWN."""
    if not message:
        return "UNKNOWN"
    match = re.match(r"^([A-Z][A-Z0-9_]{2,}):", message)
    return match.group(1) if match else "UNKNOWN"


def number(value) -> float | None:
    """NaN/inf → None, чтобы JSON не содержал нечисловых значений."""
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and result not in (float("inf"), float("-inf")) else None
