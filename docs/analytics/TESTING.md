# Тестирование

## Backend
```
pytest tests --ignore=tests/test_airflow_dags.py
ruff check backend tests airflow
```
`tests/test_analytics_dashboards.py` (34 теста) выполняет настоящий прогон pipeline на хорошем и «сломанном» наборах, строит витрины, обучает модель, делает inference и мониторинг, затем проверяет все новые endpoints: контракты, фильтры, пагинацию, сортировку, невалидные даты и идентификаторы, отсутствие трассировок и абсолютных путей в ошибках, пустые состояния.

## Frontend
```
cd frontend
npm ci
npx eslint .
npm test
npm run build
```
Vitest + Testing Library + jsdom: утилиты форматирования и серий, построители ECharts-опций, API-клиент (envelope, ошибки, abort), общие компоненты, `useAsync` (гонки запросов), страницы дашбордов (замоканный analyticsApi и EChart; loading/empty/error, фильтры, таблицы).

## CI
`.github/workflows/ci.yml`: backend, frontend (Node 22: ci, lint, test, build).

## Не покрыто
Docker-сборка, Airflow DAG-тесты и визуальные регрессии автоматически не прогоняются. Ручная проверка проводилась в браузере (Playwright) на реальных данных.
