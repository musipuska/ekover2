# Data Dictionary

Описание полей curated-слоя (`gold/.../published/measurements`) и технических полей.
Для реального датасета (USGS Water Services / Water Quality Portal) названия столбцов
приводятся к `snake_case` на уровне Silver.

## Измерения (после нормализации)

| Поле | Тип | Описание | Допустимые значения / правила |
|---|---|---|---|
| `station_id` | string | Идентификатор станции (USGS `site_no`) | not_null |
| `measured_at` | timestamp | Время измерения (UTC) | valid_timestamp, not_in_future |
| `ph` | double | Кислотность воды | between 0 и 14 |
| `temperature` | double | Температура воды, °C | between -5 и 60 |
| `turbidity` | double | Мутность, FNU | ≥ 0 |
| `dissolved_oxygen` | double | Растворённый кислород, мг/л | ≥ 0 |

## Технические поля (Bronze)

| Поле | Описание |
|---|---|
| `_dataset_id`, `_version_id`, `_batch_id` | Идентификаторы загрузки |
| `_ingested_at` | Время приёма в Bronze |
| `_source_file` | Имя исходного файла |
| `_source_row_number` | Номер строки в исходном файле (1..N) |
| `_record_hash` | SHA-256 содержимого строки (для дедупликации `record_hash`) |

## Артефакты слоя

`data/<layer>/dataset_id=X/batch_id=Y/`: `versions/<attempt_id>/` (неизменяемые версии),
`current.json` (атомарный указатель на активную версию), `manifest.json`,
для gold — `profile.json`, `quality_report.json`.

## Quality report

`quality_score` — доля пройденных правил от всех настроенных (пропущенные не считаются пройденными);
`rule_coverage` — доля реально выполненных правил; `critical_failures` — число проваленных critical-правил
(при ≥1 score = 0).

## Источник данных

Скрипт `experiments/fetch_usgs.py` скачивает суточные значения USGS (pH, температура, мутность, O₂)
по списку станций в CSV, совместимый с пайплайном. Запускается вне песочницы с доступом в интернет.
