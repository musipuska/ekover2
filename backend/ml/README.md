# ML

Первый use case — обнаружение аномальных измерений (Isolation Forest). Результат — сигнал для проверки, а не вывод о безопасности воды;
`anomaly_score` не является вероятностью нарушения нормативов.

- `anomaly_detection.py` — исходный baseline `detect_anomalies` (из патча), без сохранения модели.
- `features.py` — признаки: параметры, время (hour/day_of_week/month/season, интервал между измерениями), rolling mean/std/отклонение.
  Rolling считается по `shift(1)`, будущие значения не используются.
- `model.py` — `AnomalyDetector` (imputer + IsolationForest), статистики обучения и объяснение top-k признаков.
- `evaluation.py` — временной train/test split, метрики без разметки (доля аномалий, квантили score, чувствительность) и с разметкой (precision/recall/F1/PR-AUC/ROC-AUC).
- `registry.py` — файловый реестр `data/artifacts/models/<name>/vN`, статусы candidate → staging → production → archived.
  В production переводит только `approved_by`; новая модель всегда создаётся как candidate.
- `training.py`, `inference.py`, `monitoring.py` — обучение, batch inference в `data/predictions/...`, PSI-дрейф признаков.

Обучение и inference допускаются только для batch с опубликованным Gold и quality_status ≠ failed.
Без колонки времени модель оценивается на обучающих данных, это отражено в `evaluation.warning`.
