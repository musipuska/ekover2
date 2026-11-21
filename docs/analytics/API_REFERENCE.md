# API reference: аналитика

Префикс `/api/v1/analytics`. Ответ `{status, data, metadata}`; ошибка `{status:"error", error:{code,message,details}}`. Общие параметры: `dataset_id`, `date_from`, `date_to` (YYYY-MM-DD, иначе 422). Подробные схемы: Swagger `/docs`.

## Существующие (без изменений)
`GET /overview`, `/datasets`, `/datasets/{id}/parameters|stations|trends|quality`

## Overview
`GET /summary`

## Water Quality
`GET /water/catalog?dataset_id&batch_id`
`GET /water/distribution?dataset_id&parameter&station_id&date_from&date_to&bins`
`GET /water/correlation?dataset_id&method=pearson|spearman&min_periods`
`GET /water/thresholds`
`GET /water/measurements?dataset_id&parameter&station_id&limit&offset`

## Data Quality
`GET /quality/overview`
`GET /quality/rules?dataset_id&batch_id&status&severity&rule_type&search&sort_by&sort_dir&limit&offset`
`GET /quality/columns?dataset_id&batch_id`

## ML
`GET /ml/overview`
`GET /ml/anomalies/summary?dataset_id&batch_id&model_name&model_version`
`GET /ml/anomalies/series?dataset_id&batch_id&parameter&station_id&max_points`
`GET /ml/anomalies/scatter?dataset_id&batch_id&parameter_x&parameter_y&station_id&max_points`
`GET /ml/anomalies/records?dataset_id&batch_id&station_id&limit&offset`
`GET /ml/models/{model_name}`
`GET /ml/runs?kind&status&limit`
`GET /ml/drift?model_name&dataset_id`

## Pipeline
`GET /pipeline/overview`
`GET /pipeline/performance`
`GET /pipeline/jobs?dataset_id&status&search&sort_by&sort_dir&limit&offset`
`GET /pipeline/jobs/{job_id}`
`GET /pipeline/errors?limit`

Коды ошибок: `INVALID_DATE`, `INVALID_RANGE`, `ANALYTICS_NOT_FOUND`, 422 для невалидных параметров. Сообщения очищены от путей и traceback.
