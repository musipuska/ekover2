import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.etl.common.exceptions import StorageError
from backend.etl.common.run_context import RunContext


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
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


def read_manifest(ctx: RunContext, layer: str) -> dict | None:
    return read_json(ctx.manifest_path(layer))


def is_published(ctx: RunContext, layer: str) -> bool:
    manifest = read_manifest(ctx, layer)
    return bool(
        manifest
        and manifest.get("status") == "published"
        and manifest.get("run_key") == ctx.run_key
        and ctx.published_dir(layer).is_dir()
    )


def discard_staging(ctx: RunContext, layer: str) -> None:
    shutil.rmtree(ctx.staging_dir(layer), ignore_errors=True)


def publish_layer(ctx: RunContext, layer: str, stats: dict | None = None) -> dict:
    staging = ctx.staging_dir(layer)
    published = ctx.published_dir(layer)
    layer_dir = ctx.layer_dir(layer)

    if not staging.is_dir() or not any(staging.iterdir()):
        raise StorageError(
            "Staging пуст, публиковать нечего",
            {"layer": layer, "path": str(staging)},
        )

    archived_to = None
    try:
        if published.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            archived_to = layer_dir / "_archive" / stamp
            archived_to.parent.mkdir(parents=True, exist_ok=True)
            os.replace(published, archived_to)
        os.replace(staging, published)
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
        "schema_version": ctx.schema_version,
        "path": str(published),
        "archived_previous": str(archived_to) if archived_to else None,
        "published_at": utc_now(),
        **(stats or {}),
    }
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
        "published_at": utc_now(),
        **(stats or {}),
    }
    write_json_atomic(ctx.manifest_path(layer), manifest)
    return manifest


def apply_retention(ctx: RunContext, layer: str, keep: int = 3) -> list[str]:
    archive = ctx.layer_dir(layer) / "_archive"
    if not archive.is_dir():
        return []
    items = sorted(item for item in archive.iterdir() if item.is_dir())
    removed = []
    for item in items[: max(len(items) - keep, 0)]:
        shutil.rmtree(item, ignore_errors=True)
        removed.append(item.name)
    return removed
