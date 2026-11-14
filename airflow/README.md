# Airflow orchestration

DAG-и вызывают функции `backend.etl.orchestration`, `backend.analytics.tasks`, `backend.ml.tasks`.
Тяжёлые импорты (Spark, sklearn) выполняются внутри задач, поэтому парсинг DAG лёгкий.

| DAG | Назначение |
|---|---|
| `ekover_etl` | validate_source → build_bronze → build_silver → quality_gate → build_gold → finalize → trigger_analytics / trigger_ml |
| `ekover_analytics` | check_gold_availability → build_marts → validate_marts |
| `ekover_ml` | check_quality_gate → train_model (если `train: true`) → batch_inference → monitor_model_output |
| `ekover_csv_to_lake` | исходный one-task DAG из патча, вызывает `run_etl` целиком |

## Конфигурация запуска (`dag_run.conf`)

```json
{"dataset_id": "...", "version_id": "...", "job_id": "...", "batch_id": "...", "force": false}
```

`ekover_analytics` и `ekover_ml` принимают `dataset_id` и `batch_id`; для ML дополнительно
`train`, `model_name`, `model_version`, `allow_candidate`, `contamination`, `feature_config`.

## Семантика retry

- Ошибки с `retryable=True` (`StorageError`, `InfrastructureError`) → обычный retry.
- `ValidationError`, `SchemaError`, `QualityGateError` → `AirflowFailException`, без retry.
- Повтор задач безопасен: опубликованный слой пропускается (по `run_key` в manifest), `force=true` пересобирает слой, предыдущая версия уходит в `_archive`.
- Ошибка всего DAG run помечает `ETLJob` и `Dataset` как `failed`.

## Запуск из backend

`ORCHESTRATOR=airflow` + `AIRFLOW_API_URL`, `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD` — загрузка CSV создаёт DAG run `ekover_etl` через REST API
(`dag_run_id=api__<job_id>` сохраняется в `etl_jobs.orchestrator_run_id`). По умолчанию `ORCHESTRATOR=local` (подпроцесс, как раньше).

## Требования

Airflow 2.10.x по официальному constraints-файлу, `PYTHONPATH` = корень репозитория, общий том `DATA_LAKE_PATH` для всех воркеров,
Java + PySpark в окружении воркера. Для нескольких воркеров нужен общий объектный storage (S3/MinIO), локальный диск не подойдёт.
