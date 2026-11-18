# Data lineage

```
Upload -> raw -> Bronze (Spark) -> Silver (очистка, дедупликация) -> Quality gate -> Gold
                                                          |                 |
                                              quality_report.json     analytics marts (pandas -> parquet)
                                              data_quality_results            |
                                                                      ML: features -> train -> registry
                                                                              -> predictions -> PSI drift
```

| Показатель | Источник |
|---|---|
| Статус/длительность job | таблица `etl_jobs` |
| Rows Bronze/Silver/Gold, quarantine | `manifest.json`, `quality_report.json`, `data_assets` |
| Результаты правил | `data_quality_results` |
| Пропуски по колонкам | `profile.json` каждого batch |
| Измерения (распределения, корреляции, таблица) | gold parquet |
| Тренды, станции, параметры | `data/analytics/<mart>/dataset_id=…/batch_id=…/data.parquet` |
| Аномалии | predictions parquet (`artifacts/…`) |
| Модели | файловый реестр `artifacts/models/<name>/vN` |
| Drift | `monitoring/ml/…` (PSI, пороги 0.1 / 0.25) |
| Запуски ML | `artifacts/ml_runs` |

## Чего в lineage нет
- Времён начала/конца отдельных этапов (хранится только общее время job и длительности Spark-этапов из metrics).
- Статусов DAG-run из Airflow (backend только запускает DAG и хранит run id).
- Таблиц станций и параметров: маппинг колонок определяется автоматически.
