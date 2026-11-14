from datetime import timedelta

try:
    from airflow.sdk import DAG, get_current_context, task
except ImportError:
    from airflow import DAG
    from airflow.decorators import task
    from airflow.operators.python import get_current_context

try:
    from airflow.sdk.exceptions import AirflowFailException
except ImportError:
    from airflow.exceptions import AirflowFailException

from airflow.exceptions import AirflowException

DEFAULT_ARGS = {
    "owner": "ekover",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "execution_timeout": timedelta(hours=2),
}


def dag_conf() -> dict:
    context = get_current_context()
    dag_run = context.get("dag_run")
    return dict((dag_run.conf if dag_run else None) or {})


def run_id() -> str | None:
    dag_run = get_current_context().get("dag_run")
    return getattr(dag_run, "run_id", None)


def guarded(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except (AirflowException, AirflowFailException):
        raise
    except Exception as error:
        retryable = bool(getattr(error, "retryable", False))
        if retryable:
            raise AirflowException(str(error)) from error
        raise AirflowFailException(str(error)) from error

__all__ = ["DAG", "task", "get_current_context", "AirflowFailException", "AirflowException", "DEFAULT_ARGS", "dag_conf", "run_id", "guarded"]
