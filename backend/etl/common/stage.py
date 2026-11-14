import logging
import time
from contextlib import contextmanager
from typing import Callable, TypeVar

from backend.etl.common.exceptions import ETLError, StorageError, TransformationError
from backend.etl.common.logging import log_event
from backend.etl.common.run_context import RunContext

T = TypeVar("T")
logger = logging.getLogger("etl.stage")


def run_stage(ctx: RunContext, stage: str, func: Callable[[], T]) -> T:
    started = time.perf_counter()
    log_event(logger, f"Stage {stage} started", ctx, stage=stage)
    try:
        result = func()
    except ETLError as error:
        log_event(
            logger,
            f"Stage {stage} failed",
            ctx,
            level=logging.ERROR,
            stage=stage,
            error=error.to_dict(),
        )
        raise
    except OSError as error:
        raise StorageError(str(error), {"stage": stage}) from error
    except Exception as error:
        log_event(
            logger,
            f"Stage {stage} failed",
            ctx,
            level=logging.ERROR,
            stage=stage,
            error=str(error),
        )
        raise TransformationError(str(error), {"stage": stage}) from error
    duration = round(time.perf_counter() - started, 3)
    log_event(logger, f"Stage {stage} finished", ctx, stage=stage, duration_seconds=duration)
    return result


@contextmanager
def timed(metrics: dict, name: str):
    started = time.perf_counter()
    try:
        yield
    finally:
        metrics[name] = round(time.perf_counter() - started, 3)
