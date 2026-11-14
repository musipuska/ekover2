import os
import sys

import pendulum

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ekover_common import DAG, DEFAULT_ARGS, dag_conf, guarded, run_id, task

try:
    from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
except ImportError:
    from airflow.operators.trigger_dagrun import TriggerDagRunOperator


def on_dag_failure(context) -> None:
    from backend.etl import orchestration

    dag_run = context.get("dag_run")
    conf = dict((dag_run.conf if dag_run else None) or {})
    reason = context.get("reason") or "DAG run failed"
    try:
        orchestration.task_mark_failed(conf, reason)
    except Exception:
        pass


with DAG(
    dag_id="ekover_etl",
    description="ЭКОВЕР: validate → bronze → silver → quality gate → gold",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=4,
    default_args=DEFAULT_ARGS,
    on_failure_callback=on_dag_failure,
    tags=["ekover", "etl", "spark"],
) as dag:

    @task
    def validate_source():
        from backend.etl import orchestration

        return guarded(orchestration.task_validate_source, dag_conf(), run_id())

    @task
    def build_bronze():
        from backend.etl import orchestration

        return guarded(orchestration.task_build_bronze, dag_conf())

    @task
    def build_silver():
        from backend.etl import orchestration

        return guarded(orchestration.task_build_silver, dag_conf())

    @task
    def quality_gate():
        from backend.etl import orchestration

        return guarded(orchestration.task_quality_gate, dag_conf())

    @task
    def build_gold():
        from backend.etl import orchestration

        return guarded(orchestration.task_build_gold, dag_conf())

    @task
    def finalize(gate: dict):
        from backend.etl import orchestration

        return guarded(orchestration.task_finalize, dag_conf(), gate.get("quality_status"))

    gate = quality_gate()
    gold = build_gold()
    done = finalize(gate)

    validate_source() >> build_bronze() >> build_silver() >> gate >> gold >> done

    downstream = {
        "dataset_id": "{{ dag_run.conf['dataset_id'] }}",
        "batch_id": "{{ dag_run.conf['batch_id'] }}",
    }
    trigger_analytics = TriggerDagRunOperator(
        task_id="trigger_analytics",
        trigger_dag_id="ekover_analytics",
        conf=downstream,
        wait_for_completion=False,
    )
    trigger_ml = TriggerDagRunOperator(
        task_id="trigger_ml",
        trigger_dag_id="ekover_ml",
        conf=downstream,
        wait_for_completion=False,
    )
    done >> [trigger_analytics, trigger_ml]
