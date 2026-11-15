# Статус реализации относительно плана

Сделано: этапы 2, 3, 5 (ядро), 4 (DAG-и), 6 (витрины на Parquet + API, без dbt/PostgreSQL warehouse), 7 (ML без MLflow), частично 9 (CI).

Не сделано: миграция на PostgreSQL и Alembic (добавлен `ensure_schema` для SQLite/Postgres), MinIO и Docker Compose, dbt, MLflow,
Prometheus/Grafana, OpenLineage, аутентификация API, frontend для аналитики и ML, Delta Lake.


## Блок «до 10/10» (ноябрь 2026)

Сделано: атомарная публикация (`versions/` + `current.json`, откат, чек-суммы), строгие critical-правила и Rule Coverage,
потоковая загрузка, нумерация строк без RDD, API-ключ для смены статуса модели, раздельные статусы ETL/Analytics/ML/Pipeline,
чтение аналитики по партициям, настраиваемая дедупликация, Docker Compose, Alembic, E2E-тест, Data Dictionary,
эксперименты (`experiments/`).

Не сделано: прогон на реальном датасете USGS (нужен интернет; скрипт `experiments/fetch_usgs.py`),
страницы фронтенда (качество по batch, тренды, аномалии), запуск `docker compose up` не проверялся в песочнице (нет Docker).
