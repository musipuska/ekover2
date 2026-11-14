import os
import sys

import pendulum

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ekover_common import DAG, DEFAULT_ARGS, dag_conf, guarded, task

with DAG(
    dag_id="ekover_ml",
    description="ЭКОВЕР: признаки, обучение (опционально), batch inference, мониторинг",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=2,
    default_args=DEFAULT_ARGS,
    tags=["ekover", "airflow", "ml"],
) as dag:

    @task
    def check_quality_gate():
        from backend.ml import tasks

        return guarded(tasks.task_check_data, dag_conf())

    @task
    def train_model():
        from backend.ml import tasks

        conf = dag_conf()
        if not conf.get("train"):
            return {"model_version": None}
        return guarded(tasks.task_train, conf)

    @task
    def batch_inference(trained: dict):
        from backend.ml import tasks

        return guarded(tasks.task_inference, dag_conf(), trained.get("model_version"))

    @task
    def monitor_model_output(scored: dict):
        from backend.ml import tasks

        return guarded(tasks.task_monitor, dag_conf(), scored.get("model_version"))

    trained = train_model()
    scored = batch_inference(trained)
    check_quality_gate() >> trained
    scored >> monitor_model_output(scored)
