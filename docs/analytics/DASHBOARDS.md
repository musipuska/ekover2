# Дашборды

Навигация: боковое меню, группа «АНАЛИТИКА». Состояние страницы синхронизируется с `location.hash`. Общие фильтры (набор данных, период) хранятся в `DashboardProvider`.

| Дашборд | Файл | Источники |
|---|---|---|
| Executive Overview | `pages/OverviewDashboard.jsx` | `/analytics/summary`, `/datasets/{id}/trends`, `/water/catalog` |
| Water Quality | `pages/WaterQualityDashboard.jsx` | `/water/*`, `/datasets/{id}/stations` |
| Data Quality | `pages/DataQualityDashboard.jsx` | `/quality/overview`, `/quality/rules`, `/quality/columns` |
| ML & Anomalies | `pages/MLAnalyticsDashboard.jsx` | `/ml/*` |
| ETL & Pipeline | `pages/PipelineDashboard.jsx` | `/pipeline/*` |

## Overview
8 KPI, статус платформы (healthy / warning / degraded / no_data с причинами), активность загрузок и обработки, распределение качества, аномалии по станциям, последние наборы, jobs, quality reports и ошибки.

## Water Quality
Динамика параметра (min/avg/max, станции), гистограмма и boxplot, перцентили, подсчёт выходов за диапазоны валидности, корреляционная матрица (pearson/spearman), таблица измерений с пагинацией.

## Data Quality
Score, статусы, тренд по batch, рейтинг наборов, Bronze/Silver/Gold как независимые измерения, дубликаты, пропуски по колонкам и их динамика, таблица правил (failure rate только для row-правил).

## ML & Anomalies
KPI детекции, временной ряд с маркерами аномалий (нормальные точки прореживаются, аномалии — никогда), scatter, распределение score, аномалии по станциям и параметрам, таблица аномальных записей, реестр моделей, PSI drift, запуски обучения/inference.

## ETL & Pipeline
KPI jobs, жизненный цикл выбранной задачи (Upload → Bronze → Silver → Quality gate → Gold → Analytics → ML), тренды длительности/объёма/ошибок, длительность этапов, таблица ошибок, таблица jobs с серверным поиском, сортировкой и пагинацией.

## Состояния
Каждый блок имеет loading (skeleton), empty («Нет данных» + подсказка) и error (санитизированное сообщение + повтор). Устаревшие ответы отбрасываются через AbortController и сверку ключа запроса.
