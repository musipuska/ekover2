import pandas as pd
import pytest

from backend.ml.anomaly_detection import detect_anomalies


def test_detect_anomalies_preserves_rows_and_adds_scores():
    frame = pd.DataFrame({
        "ph": [7.0] * 19 + [14.0],
        "temperature": [20.0] * 20,
        "station": [f"s{i}" for i in range(20)],
    })

    result = detect_anomalies(
        frame,
        feature_columns=["ph", "temperature"],
        contamination=0.05,
    )

    assert len(result) == len(frame)
    assert result["is_anomaly"].dtype == bool
    assert result["anomaly_score"].notna().all()
    assert "station" in result.columns
    assert "is_anomaly" not in frame.columns


def test_rejects_missing_feature():
    with pytest.raises(ValueError, match="Unknown feature"):
        detect_anomalies(pd.DataFrame({"ph": range(10)}), ["temperature"])


def test_rejects_too_few_rows():
    with pytest.raises(ValueError, match="At least 5 rows"):
        detect_anomalies(pd.DataFrame({"ph": [7.0, 7.1, 7.2]}))
