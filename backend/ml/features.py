from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

FEATURE_VERSION = "1.0"
IDENTIFIER_COLUMNS = ("_record_hash", "_source_row_number")


@dataclass
class FeatureConfig:
    timestamp_column: str | None = None
    station_column: str | None = None
    parameter_columns: list[str] | None = None
    exclude_columns: list[str] = field(default_factory=list)
    rolling_window: int = 24
    min_periods: int = 3
    version: str = FEATURE_VERSION

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "FeatureConfig":
        known = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in payload.items() if key in known})


def select_parameters(df: pd.DataFrame, config: FeatureConfig) -> list[str]:
    if config.parameter_columns is not None:
        missing = [name for name in config.parameter_columns if name not in df.columns]
        if missing:
            raise ValueError(f"Unknown parameter columns: {missing}")
        return list(config.parameter_columns)

    skip = set(config.exclude_columns)
    skip.update(name for name in (config.timestamp_column, config.station_column) if name)
    selected = [
        name
        for name in df.columns
        if not name.startswith("_")
        and name not in skip
        and pd.api.types.is_numeric_dtype(df[name])
        and not pd.api.types.is_bool_dtype(df[name])
        and df[name].notna().any()
    ]
    if not selected:
        raise ValueError("No numeric parameter columns available for features")
    return selected


def _season(month: pd.Series) -> pd.Series:
    return month.map({12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2}).fillna(3)


def build_features(df: pd.DataFrame, config: FeatureConfig) -> tuple[pd.DataFrame, list[str]]:
    if df.empty:
        raise ValueError("Cannot build features from an empty frame")

    data = df.copy()
    parameters = select_parameters(data, config)
    data[parameters] = data[parameters].replace([np.inf, -np.inf], np.nan)

    has_time = bool(config.timestamp_column and config.timestamp_column in data.columns)
    station = config.station_column if config.station_column in data.columns else None

    if has_time:
        data["_ts"] = pd.to_datetime(data[config.timestamp_column], errors="coerce", utc=True)
        sort_keys = ([station] if station else []) + ["_ts"]
        data = data.sort_values(sort_keys, kind="stable")

    features = pd.DataFrame(index=data.index)
    for name in parameters:
        features[name] = data[name].astype("float64")

    if has_time:
        ts = data["_ts"]
        features["hour"] = ts.dt.hour
        features["day_of_week"] = ts.dt.dayofweek
        features["month"] = ts.dt.month
        features["season"] = _season(ts.dt.month)
        grouped_ts = ts.groupby(data[station]) if station else ts
        previous = grouped_ts.shift(1) if station else ts.shift(1)
        features["time_since_previous_s"] = (ts - previous).dt.total_seconds()

        window, min_periods = config.rolling_window, config.min_periods
        for name in parameters:
            series = data[name].astype("float64")
            if station:
                shifted = series.groupby(data[station]).shift(1)
                roller = shifted.groupby(data[station])
                mean = roller.transform(lambda s: s.rolling(window, min_periods=min_periods).mean())
                std = roller.transform(lambda s: s.rolling(window, min_periods=min_periods).std())
            else:
                shifted = series.shift(1)
                mean = shifted.rolling(window, min_periods=min_periods).mean()
                std = shifted.rolling(window, min_periods=min_periods).std()
            features[f"{name}_roll_mean"] = mean
            features[f"{name}_roll_std"] = std
            features[f"{name}_dev"] = series - mean

    feature_names = list(features.columns)
    meta_columns = [name for name in IDENTIFIER_COLUMNS if name in data.columns]
    for name in (config.timestamp_column, station):
        if name and name in data.columns and name not in meta_columns:
            meta_columns.append(name)

    result = pd.concat([data[meta_columns], features], axis=1)
    return result.sort_index(), feature_names
