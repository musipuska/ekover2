import os
import sys

import pendulum

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ekover_common import DAG, DEFAULT_ARGS, dag_conf, guarded, task

with DAG(
    dag_id="ekover_analytics",
    description="ЭКОВЕР: аналитические витрины поверх Gold",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=4,
    default_args=DEFAULT_ARGS,
    tags=["ekover", "airflow", "analytics"],
) as dag:

    @task
    def check_gold_availability():
        from backend.analytics import tasks

        return guarded(tasks.task_check_gold, dag_conf())

    @task
    def build_marts():
        from backend.analytics import tasks

        return guarded(tasks.task_build_marts, dag_conf())

    @task
    def validate_marts():
        from backend.analytics import tasks

        return guarded(tasks.task_validate_marts, dag_conf())

    check_gold_availability() >> build_marts() >> validate_marts()
