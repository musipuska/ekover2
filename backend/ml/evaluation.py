import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

SENSITIVITY_LEVELS = (0.01, 0.02, 0.05)


def temporal_split(
    frame: pd.DataFrame,
    timestamp_column: str,
    train_fraction: float = 0.7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be in (0, 1)")
    stamps = pd.to_datetime(frame[timestamp_column], errors="coerce", utc=True)
    valid = frame.loc[stamps.notna()].assign(_split_ts=stamps[stamps.notna()])
    if valid.empty:
        raise ValueError("No valid timestamps for temporal split")
    ordered = valid.sort_values("_split_ts", kind="stable")
    boundary = ordered["_split_ts"].iloc[max(int(len(ordered) * train_fraction) - 1, 0)]
    train = ordered[ordered["_split_ts"] <= boundary]
    test = ordered[ordered["_split_ts"] > boundary]
    return train.drop(columns="_split_ts"), test.drop(columns="_split_ts")


def unsupervised_report(
    train_scores: np.ndarray,
    train_flags: np.ndarray,
    test_scores: np.ndarray | None = None,
    test_flags: np.ndarray | None = None,
) -> dict:
    report = {
        "train_rows": int(len(train_scores)),
        "train_anomaly_rate": float(np.mean(train_flags)),
        "train_score_quantiles": {
            str(q): float(np.quantile(train_scores, q)) for q in (0.01, 0.05, 0.5, 0.95)
        },
    }
    if test_scores is not None and len(test_scores):
        report["test_rows"] = int(len(test_scores))
        report["test_anomaly_rate"] = float(np.mean(test_flags))
        report["rate_shift"] = float(np.mean(test_flags) - np.mean(train_flags))
        report["test_score_quantiles"] = {
            str(q): float(np.quantile(test_scores, q)) for q in (0.01, 0.05, 0.5, 0.95)
        }
        report["contamination_sensitivity"] = {
            str(level): float(np.mean(test_scores <= np.quantile(train_scores, level)))
            for level in SENSITIVITY_LEVELS
        }
    return report


def supervised_report(y_true: np.ndarray, scores: np.ndarray, flags: np.ndarray) -> dict:
    y_true = np.asarray(y_true).astype(int)
    if len(np.unique(y_true)) < 2:
        return {"warning": "Only one class present in labels; metrics are undefined"}
    matrix = confusion_matrix(y_true, flags.astype(int), labels=[0, 1])
    return {
        "precision": float(precision_score(y_true, flags, zero_division=0)),
        "recall": float(recall_score(y_true, flags, zero_division=0)),
        "f1": float(f1_score(y_true, flags, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, -scores)),
        "roc_auc": float(roc_auc_score(y_true, -scores)),
        "confusion_matrix": matrix.tolist(),
    }
