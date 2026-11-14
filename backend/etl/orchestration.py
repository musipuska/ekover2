from backend.etl.common.config import load_pipeline_config
from backend.etl.common.exceptions import ETLError, ValidationError
from backend.etl.common.metadata import (
    mark_job_finished,
    set_dataset_status,
)
from backend.etl.common.publish import read_json
from backend.etl.common.run_context import RunContext

REQUIRED_CONF_KEYS = ("dataset_id", "version_id", "job_id", "batch_id")


def context_from_conf(conf: dict | None, orchestrator_run_id: str | None = None) -> RunContext:
    conf = conf or {}
    missing = [
        key for key in REQUIRED_CONF_KEYS
        if not isinstance(conf.get(key), str) or not conf[key].strip()
    ]
    if missing:
        raise ValidationError(
            "Missing or empty DAG run configuration fields: " + ", ".join(missing),
            {"missing": missing},
        )
    return RunContext.from_ids(
        conf["dataset_id"],
        conf["version_id"],
        conf["job_id"],
        conf["batch_id"],
        orchestrator_run_id=orchestrator_run_id,
    )


def is_forced(conf: dict | None) -> bool:
    return bool((conf or {}).get("force", False))


def task_validate_source(conf: dict, orchestrator_run_id: str | None = None) -> dict:
    from backend.etl.jobs.ingestion import validate_source

    ctx = context_from_conf(conf, orchestrator_run_id)
    info = validate_source(ctx, load_pipeline_config())
    return {"encoding": info["encoding"], "size": info["file_size_bytes"]}


def task_build_bronze(conf: dict) -> dict:
    from backend.etl.jobs.bronze_job import run_bronze

    manifest = run_bronze(context_from_conf(conf), force=is_forced(conf))
    return {"layer": "bronze", "row_count": manifest["row_count"], "path": manifest["path"]}


def task_build_silver(conf: dict) -> dict:
    from backend.etl.jobs.silver_job import run_silver

    manifest = run_silver(context_from_conf(conf), load_pipeline_config(), force=is_forced(conf))
    return {"layer": "silver", "row_count": manifest["row_count"], "path": manifest["path"]}


def task_quality_gate(conf: dict) -> dict:
    from backend.etl.jobs.quality_job import run_quality

    report = run_quality(context_from_conf(conf), load_pipeline_config(), force=is_forced(conf))
    return {
        "quality_status": report["quality_status"],
        "quality_score": report["quality_score"],
        "quarantined_rows": report["quarantined_rows"],
    }


def task_build_gold(conf: dict) -> dict:
    from backend.etl.jobs.gold_job import run_gold

    manifest = run_gold(context_from_conf(conf), load_pipeline_config(), force=is_forced(conf))
    return {
        "layer": "gold",
        "row_count": manifest["row_count"],
        "quality_status": manifest["quality_status"],
    }


def task_finalize(conf: dict, quality_status: str | None = None) -> dict:
    ctx = context_from_conf(conf)
    mark_job_finished(ctx.job_id, "success", None, quality_status)
    set_dataset_status(ctx.dataset_id, "success")
    return {"status": "success", "job_id": ctx.job_id}


def task_mark_failed(conf: dict, error: BaseException | str | None) -> dict:
    ctx = context_from_conf(conf)
    if isinstance(error, ETLError):
        message = f"{error.code}: {error.message}"
    else:
        message = str(error) if error else "Unknown failure"
    report = read_json(ctx.layer_dir("gold") / "quality_report.json")
    quality_status = report.get("quality_status") if report else None
    mark_job_finished(ctx.job_id, "failed", message, quality_status)
    set_dataset_status(ctx.dataset_id, "failed")
    return {"status": "failed", "message": message}


def is_retryable(error: BaseException) -> bool:
    return bool(getattr(error, "retryable", True))
