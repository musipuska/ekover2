import json
import os
import tempfile
from pathlib import Path

POINTER_NAME = "current.json"
VERSIONS_DIR = "versions"
NO_VERSION = "_none"


def pointer_path(layer_dir: Path) -> Path:
    return layer_dir / POINTER_NAME


def read_pointer(layer_dir: Path) -> dict | None:
    path = pointer_path(layer_dir)
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and payload.get("attempt_id") else None


def version_path(layer_dir: Path, attempt_id: str) -> Path:
    return layer_dir / VERSIONS_DIR / attempt_id


def resolve_published(layer_dir: Path) -> Path:
    pointer = read_pointer(layer_dir)
    if pointer is None:
        return layer_dir / VERSIONS_DIR / NO_VERSION
    return version_path(layer_dir, pointer["attempt_id"])


def write_pointer(layer_dir: Path, payload: dict) -> None:
    target = pointer_path(layer_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
