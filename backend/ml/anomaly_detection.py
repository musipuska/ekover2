"""Unsupervised anomaly detection for numeric water-sensor measurements.

This is a reusable baseline, not a production water-quality compliance model.
Train/calibrate it on representative historical measurements before operational use.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline


def detect_anomalies(
    data: pd.DataFrame,
    feature_columns: Sequence[str] | None = None,
    *,
    contamination: float = 0.02,
    random_state: int = 42,
) -> pd.DataFrame:
    """Return a copy of *data* with anomaly labels and scores.

    `is_anomaly=True` marks observations classified as outliers by IsolationForest.
    `anomaly_score` is the model's decision_function value; lower values are more
    anomalous. Rows are not removed or modified.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if data.empty:
        raise ValueError("data must contain at least one row")
    if not 0.0 < contamination <= 0.5:
        raise ValueError("contamination must be in the interval (0, 0.5]")

    if feature_columns is None:
        selected = data.select_dtypes(include="number").columns.tolist()
    else:
        selected = list(feature_columns)
        missing = [name for name in selected if name not in data.columns]
        if missing:
            raise ValueError(f"Unknown feature columns: {missing}")
        non_numeric = [
            name for name in selected
            if not pd.api.types.is_numeric_dtype(data[name])
        ]
        if non_numeric:
            raise TypeError(f"Features must be numeric: {non_numeric}")

    selected = [
        name for name in selected
        if data[name].notna().any()
    ]
    if not selected:
        raise ValueError("No numeric features with at least one non-null value")
    if len(data) < 5:
        raise ValueError("At least 5 rows are required for anomaly detection")

    features = data[selected].replace([float("inf"), float("-inf")], np.nan)
    if features.dropna(how="all").shape[0] < 5:
        raise ValueError("At least 5 rows must contain usable feature values")

    model = make_pipeline(
        SimpleImputer(strategy="median"),
        IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        ),
    )
    predictions = model.fit_predict(features)
    scores = model.decision_function(features)

    result = data.copy()
    result["is_anomaly"] = predictions == -1
    result["anomaly_score"] = scores
    return result
