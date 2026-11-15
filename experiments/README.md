# Эксперименты

Запуск из корня репозитория (`PYTHONPATH=.`):

- `python experiments/anomaly_comparison.py` — Z-score / IQR / IsolationForest / LOF на синтетических данных
  с контролируемыми аномалиями (ROC-AUC, PR-AUC, F1, время; несколько seed, mean ± std). Результат: `results_anomaly.json`.
- `python experiments/etl_timing.py --sizes 100000 1000000` — время этапов ETL на 100k/1M строк. Результат: `results_etl_timing.json`.
- `python experiments/fetch_usgs.py ...` — загрузка реальных данных USGS (нужен интернет).
