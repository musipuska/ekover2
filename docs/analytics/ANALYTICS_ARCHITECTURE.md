# Архитектура аналитики

## Принцип
Измерения хранятся в parquet data lake, а не в БД. БД содержит только метаданные (datasets, dataset_versions, etl_jobs, data_quality_results, data_assets). Аналитика считается на лету из этих источников, ничего не дублируется и не придумывается: если данных нет, API возвращает пустой результат, а UI показывает «Нет данных» или N/A.

## Слои
```
Frontend (React + ECharts)
  pages/*Dashboard.jsx -> services/analyticsApi.js -> hooks/useAsync
Backend API   backend/app/api/v1/analytics.py   (валидация, envelope, Pydantic-контракты)
Расчёты       backend/analytics/{executive,water_stats,quality_stats,ml_stats,pipeline_stats}.py
Общее         backend/analytics/common.py       (safe_id, диапазоны дат, sanitize_error, number)
Источники     БД метаданных | parquet lake (silver/gold, profile, quality_report) | analytics marts | ML registry/predictions/drift
```

## Контракты
- Успех: `{status:"ok", data, metadata}`; ошибка: `{status:"error", error:{code,message,details}}`.
- Все ответы новых endpoints проходят через Pydantic-модели из `backend/app/schemas/analytics.py`.
- Статусы качества не менялись: `passed | warning | failed`.

## Фильтры
Dataset, date_from, date_to, station_id, parameter, batch_id, status, severity, search, sort, limit/offset реально меняют запросы на бэкенде. Некорректные даты дают 422 (INVALID_DATE / INVALID_RANGE), небезопасные идентификаторы отклоняются `safe_id`.

## Безопасность
- Идентификаторы датасетов/батчей/моделей валидируются (нет `/ \ * ? [ ]`, `.`, `..`).
- Поиск в SQL экранирует LIKE-символы.
- Сообщения об ошибках проходят `sanitize_error`: удаляются абсолютные пути и traceback, длина ≤ 300.
- Запуск DAG из фронтенда не предусмотрен.

## Решения, влияющие на достоверность
- Success rate = success / (success + failed); queued и running не учитываются.
- Дельты KPI считаются только при выбранном периоде и сравнивают с предыдущим окном такой же длины.
- Anomaly score сравнивается только внутри одной модели и версии.
- Precision/Recall не показываются: ground truth в системе отсутствует.
- Пороги берутся из конфигурации pipeline (физические диапазоны), не из санитарных норм.
