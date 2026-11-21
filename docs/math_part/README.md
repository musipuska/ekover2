# Математическая часть проекта ЭКОВЕР

Этот каталог содержит формальное математическое описание методов, которые **реально реализованы** в коде ЭКОВЕР: контроль качества данных, описательная статистика, обнаружение аномалий, валидация моделей и мониторинг дрейфа. Каждый раздел связан с конкретными файлами репозитория, содержит определения, утверждения с доказательствами, численные расчёты на данных проекта и графики. Все числа в тексте получены запуском скриптов из `scripts/` и сохранены в `results/*.json`.

## Содержание

| № | Файл | О чём | Код, к которому привязан |
|---|---|---|---|
| 1 | [01_data_model.md](01_data_model.md) | Формальная модель данных и слоёв RAW → BRONZE → SILVER → GOLD, баланс строк, пропуски | `backend/etl/transformations/`, `backend/etl/jobs/` |
| 2 | [02_quality_gate.md](02_quality_gate.md) | Правила качества как предикаты, `quality_score`, `rule_coverage`, решающая функция quality gate | `backend/etl/quality/gate.py`, `rules.py` |
| 3 | [03_descriptive_statistics.md](03_descriptive_statistics.md) | Выборочные статистики, квантили, правило Тьюки, Z-оценка, корреляции Пирсона и Спирмена | `backend/analytics/water_stats.py` |
| 4 | [04_isolation_forest.md](04_isolation_forest.md) | Isolation Forest: вывод $c(n)$, оценка аномальности, порог по `contamination` | `backend/ml/model.py`, `anomaly_detection.py` |
| 5 | [05_lof_and_detector_comparison.md](05_lof_and_detector_comparison.md) | LOF, сравнение Z-score / IQR / IF / LOF, где и почему методы ошибаются | `experiments/anomaly_comparison.py` |
| 6 | [06_features_validation_metrics.md](06_features_validation_metrics.md) | Скользящие признаки без утечки, временной сплит, метрики качества | `backend/ml/features.py`, `evaluation.py` |
| 7 | [07_drift_psi.md](07_drift_psi.md) | PSI: определение, свойства, шумовой уровень, чувствительность к дрейфу | `backend/ml/monitoring.py` |
| 8 | [08_summary_and_limitations.md](08_summary_and_limitations.md) | Сводка утверждений, ограничения, наблюдения по коду | весь проект |

## Структура каталога

```text
docs/math_part/
├── README.md
├── 01_data_model.md … 08_summary_and_limitations.md
├── figures/      графики (PNG), на которые ссылаются разделы
├── results/      числовые результаты расчётов (JSON)
└── scripts/      скрипты, которые воспроизводят все числа и графики
```

## Как воспроизвести расчёты

Из корня репозитория, с установленными `numpy`, `pandas`, `scipy`, `scikit-learn`, `matplotlib`, `pydantic-settings`:

```bash
python docs/math_part/scripts/run_all.py
```

Один скрипт отдельно, например только PSI:

```bash
python docs/math_part/scripts/run_all.py s04_psi
```

Скрипты импортируют рабочий код проекта (`backend.etl.quality.gate`, `backend.ml.monitoring`, `backend.ml.features`, `backend.ml.evaluation`, `backend.ml.anomaly_detection`, `experiments.anomaly_comparison`), поэтому совпадение формул с реализацией проверяется самим запуском. PySpark для расчётов не нужен: правила качества на Spark воспроизведены на pandas с той же семантикой, а функции `quality_score`, `rule_coverage`, `evaluate_gate` вызываются из кода проекта без изменений.

Номера в именах файлов `results/` и скриптов соответствуют скриптам, а не разделам:

| Скрипт | Файл результатов | Раздел |
|---|---|---|
| `s01_quality_score.py` | `01_quality_score.json` | 2 (и 1.6) |
| `s02_descriptive_outliers.py` | `02_descriptive_outliers.json` | 3 |
| `s03_isolation_forest.py` | `03_isolation_forest.json` | 4 |
| `s04_psi.py` | `04_psi.json` | 7 |
| `s05_detector_comparison.py` | `05_detector_comparison.json` | 5 |
| `s06_validation_features.py` | `06_validation_features.json` | 6 |
| `s07_real_data.py` | `07_real_data.json` | 4.7 |

Имена графиков в `figures/` начинаются с номера раздела, в котором они используются.

## Данные

Расчёты на реальных данных используют файл `water_potability.csv` из `data/raw/` (3 276 строк, 9 физико-химических параметров и метка `potability`). В наборе нет столбцов станции и времени, поэтому всё, что требует временной оси (скользящие признаки, временной сплит), проверяется на синтетических рядах с известной структурой. Это каждый раз указано явно.

## Обозначения

| Символ | Смысл |
|---|---|
| $n$, $m$ | число строк и число числовых параметров |
| $x_{ij}$ | значение параметра $j$ в строке $i$; пропуск обозначается $\varnothing$ |
| $\bar x$, $s$ | выборочное среднее и выборочное стандартное отклонение ($\mathrm{ddof}=1$) |
| $Q_p$ | выборочный квантиль уровня $p$ |
| $\Phi$, $\varphi$ | функция распределения и плотность $\mathcal N(0,1)$ |
| $\mathbf 1[\cdot]$ | индикатор события |
| $H_k$ | гармоническое число $\sum_{j=1}^{k}1/j$, $\gamma\approx0.5772$ — постоянная Эйлера |
| $c$ | параметр `contamination` |

## Как читать разделы

В каждом разделе одинаковая структура: **постановка** (что реализовано и где), **определения**, **утверждения и доказательства**, **расчёт на данных**, **вывод для работы** и **ограничения**. Утверждения, которые доказаны строго, помечены словом «Теорема» или «Утверждение»; эвристические объяснения, подтверждённые только экспериментом, помечены как «Наблюдение».
