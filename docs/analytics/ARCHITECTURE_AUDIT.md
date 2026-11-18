# ARCHITECTURE AUDIT — состояние EKOVER2 до внедрения дашбордов

Аудит выполнен по коммиту `93e340e` (merge PR #4, `feature/ekover-10of10`).
Все утверждения ниже получены чтением кода и запуском тестов; предположений нет.

## 1. Базовая линия (до изменений)

| Проверка | Результат |
|---|---|
| `pytest tests --ignore=tests/test_airflow_dags.py` | **49 passed** (Python 3.13, pyspark 4.3, Java 21) |
| `frontend: npm run build` | проходит |
| `frontend: npm run lint` | **падает: 5 ошибок в существующем коде** (`App.jsx`: `set-state-in-effect`, неиспользуемые импорты; `Sidebar.jsx`/`StatCard.jsx`: неиспользуемый `React`) |
| Тесты frontend | отсутствуют (нет Vitest/RTL) |

## 2. Фактическая структура

```text
backend/
  app/            FastAPI: api/v1/*, services/, repositories/, schemas/, infrastructure/{database,storage}
  etl/            PySpark: jobs/{bronze,silver,quality,gold,full_pipeline}, quality/{gate,rules,reports}, common/*
  ml/             IsolationForest: features, model, training, inference, monitoring (PSI), registry (файловый)
  analytics/      marts.py (pandas → parquet), repository.py (чтение marts), tasks.py (Airflow)
airflow/dags/     ekover_etl, ekover_analytics, ekover_ml, ekover_csv_to_lake
alembic/          одна baseline-миграция
frontend/src/     App.jsx (658 строк, переключение страниц через useState, без роутера),
                  components/{Sidebar,StatCard}, services/api.js, style.css
```

### Важные отличия от допущений в постановке

1. **Аналитические marts — не SQL.** `backend/analytics/marts.py` строит pandas-DataFrame из Gold-parquet и
   пишет parquet в `data/analytics/<mart>/dataset_id=…/batch_id=…/data.parquet`. PostgreSQL/SQLite хранит
   **только метаданные**: `datasets`, `dataset_versions`, `etl_jobs`, `data_quality_results`, `data_assets`.
   Поэтому «SQL-агрегации на PostgreSQL» применимы к jobs/quality-rules/assets, а измерения агрегируются
   из parquet (marts) или читаются из Gold.
2. **Нет сущностей «станция» и «параметр» в БД.** Станция и параметры определяются автоматически
   (`detect_mapping`): колонка станции — одна из `station_id|station|station_code|site_id`, параметры —
   числовые колонки без префикса `_`. Если в данных нет колонки станции, `station_metrics` не строится.
3. **Нормативов качества воды в проекте нет.** `etl/config/default.yaml` содержит правила `between`
   (pH 0–14, температура −5…100 и т. п.) — это *границы физической допустимости* для quality gate,
   а не санитарные нормы. В UI они подписываются именно так.
4. **Статусы quality gate — строчные:** `passed | warning | failed` (`etl/quality/gate.py`).
   Статусы ETL-джобы: `queued | running | success | failed`. Устаревшие артефакты в `data/gold/…` содержат
   `quality_status: "success"` — UI показывает неизвестные значения как есть, не подменяя их.
5. **ML-реестр файловый** (`data/artifacts/models/<name>/vN/{model.joblib,metadata.json}`), статусы
   `candidate → staging → production → archived`. Обучение — только IsolationForest (без разметки);
   `supervised_report` вызывается только при `label_column`, т. е. Precision/Recall существуют **только**
   если модель обучали на размеченном столбце. Для неразмеченных данных их показывать нельзя.
6. **Дрейф (PSI) реализован** в `ml/monitoring.py` (пороги `PSI_WARNING=0.1`, `PSI_ALERT=0.25`), отчёт пишется в
   `data/monitoring/ml/model_name=…/dataset_id=…/batch_id=….json`. В отчёте нет времени генерации.
7. **Airflow:** API только *запускает* DAG (`orchestrator_service.trigger_airflow_dag`), статус DAG-run
   обратно не опрашивается; в `etl_jobs` хранится только `orchestrator_run_id`. По умолчанию
   `ORCHESTRATOR=local` (BackgroundTask без Airflow).
8. **Статусы этапов** лежат в самой `etl_jobs`: `status` (ETL), `analytics_status`, `ml_status`,
   `pipeline_status`, `stage`, `quality_status`, `metrics` (JSON: длительности `validate_source|bronze|silver|quality|gold`
   в секундах и `rows_bronze|rows_silver|rows_gold`). **Времён начала/конца отдельных этапов нет** — только длительности.
9. **`data_quality_results`** хранит результат по каждому правилу (`failed_rows`, `observed_value`, `severity`,
   `status`, `created_at`), но **не хранит число проверенных строк** → «Checked Records» и «Failure Rate» по
   БД посчитать нельзя; допустимо считать долю только для построчных правил относительно `silver_rows` из отчёта.
10. **Закоммиченный `data/`** — устаревшие артефакты старого формата с абсолютными путями чужой машины;
    в нём нет marts, предсказаний, дрейфа. Реальные данные появляются после прогона пайплайна.

## 3. Существующие endpoints (`/api/v1`)

| Endpoint | Формат | Источник |
|---|---|---|
| `GET /datasets`, `GET /datasets/{id}` | «голые» схемы | БД |
| `POST /datasets/uploads` | 202 + ids | БД + raw |
| `GET /jobs/{id}` | `JobRead` | БД |
| `GET /datasets/{id}/profile`, `/quality/{batch}`, `/batches` | «голые» схемы | Gold JSON |
| `GET /analytics/overview`, `/datasets`, `/datasets/{id}/{parameters,stations,trends,quality}` | envelope `{status,data,metadata}` | marts / Gold |
| `GET /ml/models[/{name}]`, `/predictions`, `/anomalies[/{id}]`, `/runs/{id}`; `POST /ml/training-runs`, `/ml/inference`, `/ml/models/…/status` | envelope | реестр / parquet |

Два стиля ответа сосуществуют (голые схемы и envelope). Новые endpoints используют envelope, как `/analytics/*` и `/ml/*`.

## 4. Существующие аналитические функции (`marts.py`)

| Функция | Вход | Результат | NULL/пусто | Фильтры в API |
|---|---|---|---|---|
| `dataset_summary` | Gold df + manifest | 1 строка: rows, parameter_count, station_count, period, quality | пустой период → `None` | — |
| `parameter_metrics` | Gold df | count, null_count, mean, std, min, max, p05/p25/median/p75/p95 | NaN/inf отбрасываются, `std` при n≤1 → `None` | `batch_id` |
| `daily_metrics` | Gold df | date × station × parameter: count/avg/min/max/std/median | строки без валидного времени отбрасываются | `parameter, station_id, date_from, date_to, batch_id` |
| `station_metrics` | Gold df | station × parameter: те же агрегаты | нет станции → mart не строится | `parameter, batch_id` |

Безопасность: `repository._read_mart` отклоняет `dataset_id/batch_id` с `/ \ * ? [ ]`, `.`, `..` (защита от path traversal в glob).
Эффективность: читаются только нужные партиции; `trends` фильтрует в pandas после чтения партиции (приемлемо при дневной агрегации).

## 5. Data lineage (фактический)

```text
CSV (POST /datasets/uploads) → data/raw/<dataset>/<version>_<file>
  → ETLJob(queued) → [local BackgroundTask | Airflow DAG ekover_etl]
  → Bronze  data/bronze/…/batch_id=…   (+ _record_hash, _source_row_number)
  → Silver  data/silver/…              (очистка, дедупликация по dedup_strategy)
  → Quality gate  gold/…/quality_report.json + БД data_quality_results
  → Gold    data/gold/dataset_id=…/batch_id=…/{measurements/,manifest.json,profile.json,quality_report.json}
  → Analytics marts  data/analytics/{dataset_summary,parameter_metrics,daily_metrics,station_metrics}/…
  → ML: training → artifacts/models; inference → predictions/…; monitoring → monitoring/ml/…
  → FastAPI → React
```

## 6. Gap-анализ по дашбордам

| Дашборд | Есть | Нет → реализуем |
|---|---|---|
| Overview | `/analytics/overview` (datasets, batches, rows, quality-счётчик) | сводка jobs (успех/ошибки), средний quality score, число аномалий, активность по времени, последние датасеты/jobs/ошибки |
| Water Quality | parameters, stations, trends (дневные) | распределение (гистограмма/box/перцентили), корреляции, пороги из конфигурации |
| Data Quality | отчёт по batch, история batch, профиль колонок | агрегат по датасетам, результаты правил с фильтрами (БД), потери Bronze→Silver→Gold |
| ML & Anomalies | реестр, predictions, anomalies (плоский список), `/ml/runs/{id}` | сводка и срезы аномалий, временной ряд с маркерами, отчёты дрейфа, список запусков |
| ETL Monitoring | `GET /jobs/{id}` | список jobs (поиск/фильтр/сортировка/пагинация), агрегаты, длительности этапов, ошибки, активы по слоям |

Frontend: нет библиотеки графиков, нет роутера, нет тестов, `API_URL` захардкожен в `api.js`, клиент не понимает envelope-ошибки (`error.message`).

## 7. Технические ограничения и решения

- Один набор данных может не иметь станции/времени → соответствующие панели показывают «Нет данных» с причиной.
- Фильтры применяются только там, где backend может это сделать (см. `DASHBOARDS.md`); лишних фильтров в UI нет.
- Новые таблицы БД не нужны: всё необходимое уже есть в `etl_jobs`, `data_quality_results`, `data_assets`, marts, Gold, реестре. Миграций нет.
- Старые endpoints и контракты не меняются; `.bak`/`.backup` файлы в репозитории не трогаем.

## 8. План интеграции

1. Backend: `backend/analytics/{pipeline_stats,quality_stats,water_stats,ml_stats,executive}.py` + схемы `app/schemas/analytics.py` + новые маршруты в `api/v1/analytics.py` (envelope).
2. Frontend: Apache ECharts (одна библиотека), общие компоненты, пять страниц, общий контекст фильтров, расширенный API-клиент.
3. Тесты: pytest на каждый endpoint (на реальном прогоне пайплайна), Vitest + RTL на компоненты/страницы.
4. Документация: `ANALYTICS_ARCHITECTURE.md`, `DASHBOARDS.md`, `API_REFERENCE.md`, `DATA_LINEAGE.md`, `TESTING.md`.
