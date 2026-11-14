from pathlib import Path

import pytest

pytest.importorskip("airflow.models")

from airflow.models import DagBag

DAGS = Path(__file__).resolve().parents[1] / "airflow" / "dags"


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder=str(DAGS), include_examples=False)


def test_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_expected_dags_present(dagbag):
    assert {"ekover_etl", "ekover_analytics", "ekover_ml", "ekover_csv_to_lake"} <= set(dagbag.dag_ids)


def test_etl_dependencies(dagbag):
    dag = dagbag.get_dag("ekover_etl")
    chain = ["validate_source", "build_bronze", "build_silver", "quality_gate", "build_gold", "finalize"]
    for upstream, downstream in zip(chain, chain[1:]):
        assert downstream in dag.get_task(upstream).downstream_task_ids
    assert {"trigger_analytics", "trigger_ml"} <= dag.get_task("finalize").downstream_task_ids


def test_retries_and_timeouts(dagbag):
    for dag_id in ("ekover_etl", "ekover_analytics", "ekover_ml"):
        for task in dagbag.get_dag(dag_id).tasks:
            if task.task_id.startswith("trigger_"):
                continue
            assert task.retries >= 1
            assert task.execution_timeout is not None
