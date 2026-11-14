import logging

from backend.etl.common.config import PipelineConfig, load_pipeline_config
from backend.etl.common.logging import log_event
from backend.etl.common.metadata import (
    get_version_info,
    mark_job_started,
    set_dataset_status,
    source_path_for,
)
from backend.etl.common.run_context import RunContext
from backend.etl.common.source_validation import validate_source_file
from backend.etl.common.stage import run_stage

logger = logging.getLogger("etl.ingestion")


def validate_source(ctx: RunContext, config: PipelineConfig | None = None) -> dict:
    config = config or load_pipeline_config()

    def action() -> dict:
        mark_job_started(ctx.job_id, ctx.run_key, ctx.orchestrator_run_id)
        set_dataset_status(ctx.dataset_id, "running")
        info = get_version_info(ctx.version_id)
        source = source_path_for(info)
        validation = validate_source_file(
            source,
            expected_checksum=info["checksum"],
            required_columns=config.required_columns,
        )
        log_event(logger, "Source validated", ctx, **{k: v for k, v in validation.items() if k != "columns"})
        return {"source_uri": str(source), **validation}

    return run_stage(ctx, "validate_source", action)
