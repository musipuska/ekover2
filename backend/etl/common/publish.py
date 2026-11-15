import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.etl.common.exceptions import StorageError
from backend.etl.common.run_context import RunContext
from backend.etl.common.versions import (
    VERSIONS_DIR,
    read_pointer,
    version_path,
    write_pointer,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, path)
    except OSError as error:
        Path(temp_name).unlink(missing_ok=True)
        raise StorageError(str(error), {"path": str(path)}) from error
    return path


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def describe_files(directory: Path) -> list[dict]:
    return [
        {
            "path": str(item.relative_to(directory)).replace(os.sep, "/"),
            "size_bytes": item.stat().st_size,
            "sha256": file_sha256(item),
        }
        for item in sorted(directory.rglob("*"))
        if item.is_file()
    ]


def read_manifest(ctx: RunContext, layer: str) -> dict | None:
    return read_json(ctx.manifest_path(layer))


def is_published(ctx: RunContext, layer: str) -> bool:
    manifest = read_manifest(ctx, layer)
    pointer = read_pointer(ctx.layer_dir(layer))
    return bool(
        manifest
        and pointer
        and manifest.get("status") == "published"
        and manifest.get("run_key") == ctx.run_key
        and manifest.get("attempt_id") == pointer["attempt_id"]
        and ctx.published_dir(layer).is_dir()
    )


def verify_published(ctx: RunContext, layer: str) -> list[str]:
    manifest = read_manifest(ctx, layer)
    if not manifest or manifest.get("status") != "published":
        return ["manifest отсутствует или не published"]
    directory = ctx.published_dir(layer)
    problems = []
    for item in manifest.get("files", []):
        path = directory / item["path"]
        if not path.is_file():
            problems.append(f"файл отсутствует: {item['path']}")
        elif path.stat().st_size != item["size_bytes"] or file_sha256(path) != item["sha256"]:
            problems.append(f"контрольная сумма не совпадает: {item['path']}")
    return problems


def discard_staging(ctx: RunContext, layer: str) -> None:
    shutil.rmtree(ctx.staging_dir(layer), ignore_errors=True)


def _switch_pointer(ctx: RunContext, layer: str, previous: dict | None) -> None:
    write_pointer(
        ctx.layer_dir(layer),
        {
            "attempt_id": ctx.attempt_id,
            "run_key": ctx.run_key,
            "previous_attempt_id": previous["attempt_id"] if previous else None,
            "switched_at": utc_now(),
        },
    )


def publish_layer(ctx: RunContext, layer: str, stats: dict | None = None) -> dict:
    staging = ctx.staging_dir(layer)
    layer_dir = ctx.layer_dir(layer)
    target = ctx.version_dir(layer)

    if not staging.is_dir() or not any(staging.iterdir()):
        raise StorageError(
            "Staging пуст, публиковать нечего",
            {"layer": layer, "path": str(staging)},
        )
    if target.exists():
        raise StorageError("Версия с таким attempt_id уже существует", {"path": str(target)})

    files = describe_files(staging)
    previous = read_pointer(layer_dir)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    except OSError as error:
        raise StorageError(str(error), {"layer": layer}) from error

    manifest = {
        "layer": layer,
        "status": "published",
        "run_key": ctx.run_key,
        "dataset_id": ctx.dataset_id,
        "version_id": ctx.version_id,
        "batch_id": ctx.batch_id,
        "job_id": ctx.job_id,
        "attempt_id": ctx.attempt_id,
        "previous_attempt_id": previous["attempt_id"] if previous else None,
        "schema_version": ctx.schema_version,
        "config_checksum": ctx.config_checksum,
        "code_version": ctx.code_version,
        "path": str(target),
        "files": files,
        "published_at": utc_now(),
        **(stats or {}),
    }
    write_json_atomic(layer_dir / VERSIONS_DIR / f"{ctx.attempt_id}.manifest.json", manifest)
    _switch_pointer(ctx, layer, previous)
    write_json_atomic(ctx.manifest_path(layer), manifest)
    return manifest


def rollback_layer(ctx: RunContext, layer: str) -> dict:
    layer_dir = ctx.layer_dir(layer)
    pointer = read_pointer(layer_dir)
    if not pointer or not pointer.get("previous_attempt_id"):
        raise StorageError("Нет предыдущей версии для отката", {"layer": layer})
    previous_id = pointer["previous_attempt_id"]
    if not version_path(layer_dir, previous_id).is_dir():
        raise StorageError("Предыдущая версия удалена", {"attempt_id": previous_id})
    manifest = read_json(layer_dir / VERSIONS_DIR / f"{previous_id}.manifest.json")
    if manifest is None:
        raise StorageError("Манифест предыдущей версии не найден", {"attempt_id": previous_id})
    write_pointer(
        layer_dir,
        {
            "attempt_id": previous_id,
            "run_key": manifest["run_key"],
            "previous_attempt_id": manifest.get("previous_attempt_id"),
            "switched_at": utc_now(),
            "rolled_back_from": pointer["attempt_id"],
        },
    )
    write_json_atomic(ctx.manifest_path(layer), manifest)
    return manifest


def write_blocked_manifest(ctx: RunContext, layer: str, reason: str, stats: dict | None = None) -> dict:
    manifest = {
        "layer": layer,
        "status": "blocked",
        "reason": reason,
        "run_key": ctx.run_key,
        "dataset_id": ctx.dataset_id,
        "version_id": ctx.version_id,
        "batch_id": ctx.batch_id,
        "job_id": ctx.job_id,
        "schema_version": ctx.schema_version,
        "config_checksum": ctx.config_checksum,
        "code_version": ctx.code_version,
        "published_at": utc_now(),
        **(stats or {}),
    }
    write_json_atomic(ctx.manifest_path(layer), manifest)
    return manifest


def cleanup_orphans(ctx: RunContext, layer: str) -> list[str]:
    layer_dir = ctx.layer_dir(layer)
    removed = []
    pointer = read_pointer(layer_dir)
    current = pointer["attempt_id"] if pointer else None

    attempts = layer_dir / "_attempts"
    if attempts.is_dir():
        for item in attempts.iterdir():
            if item.name != ctx.attempt_id:
                shutil.rmtree(item, ignore_errors=True) if item.is_dir() else item.unlink(missing_ok=True)
                removed.append(f"_attempts/{item.name}")

    versions = layer_dir / VERSIONS_DIR
    if versions.is_dir():
        for item in versions.iterdir():
            if not item.is_dir() or item.name == current:
                continue
            if not (versions / f"{item.name}.manifest.json").is_file():
                shutil.rmtree(item, ignore_errors=True)
                removed.append(f"versions/{item.name}")
    return removed


def apply_retention(ctx: RunContext, layer: str, keep: int = 3) -> list[str]:
    layer_dir = ctx.layer_dir(layer)
    versions = layer_dir / VERSIONS_DIR
    pointer = read_pointer(layer_dir)
    if not versions.is_dir() or not pointer:
        return []
    protected = {pointer["attempt_id"], pointer.get("previous_attempt_id")}
    candidates = sorted(
        (item for item in versions.iterdir() if item.is_dir() and item.name not in protected),
        key=lambda item: item.stat().st_mtime,
    )
    excess = max(len(candidates) + len([p for p in protected if p]) - max(keep, 2), 0)
    removed = []
    for item in candidates[:excess]:
        shutil.rmtree(item, ignore_errors=True)
        (versions / f"{item.name}.manifest.json").unlink(missing_ok=True)
        removed.append(item.name)
    return removed
