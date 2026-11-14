import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

MIN_TRAIN_ROWS = 20


class AnomalyDetector:
    def __init__(
        self,
        contamination: float = 0.02,
        n_estimators: int = 200,
        random_state: int = 42,
    ) -> None:
        if not 0.0 < contamination <= 0.5:
            raise ValueError("contamination must be in the interval (0, 0.5]")
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.feature_names: list[str] = []
        self.stats: dict = {}
        self.pipeline = None

    def _matrix(self, frame: pd.DataFrame) -> pd.DataFrame:
        missing = [name for name in self.feature_names if name not in frame.columns]
        if missing:
            raise ValueError(f"Missing features: {missing}")
        return frame[self.feature_names].replace([np.inf, -np.inf], np.nan).astype("float64")

    def fit(self, frame: pd.DataFrame, feature_names: list[str]) -> "AnomalyDetector":
        usable = [name for name in feature_names if frame[name].notna().any()]
        if not usable:
            raise ValueError("No features with non-null values")
        self.feature_names = usable
        matrix = self._matrix(frame)
        if matrix.dropna(how="all").shape[0] < MIN_TRAIN_ROWS:
            raise ValueError(f"At least {MIN_TRAIN_ROWS} rows with usable features are required")

        self.pipeline = make_pipeline(
            SimpleImputer(strategy="median"),
            IsolationForest(
                n_estimators=self.n_estimators,
                contamination=self.contamination,
                random_state=self.random_state,
                n_jobs=-1,
            ),
        )
        self.pipeline.fit(matrix)
        self.stats = self._training_stats(matrix)
        return self

    def _training_stats(self, matrix: pd.DataFrame) -> dict:
        stats = {}
        for name in self.feature_names:
            values = matrix[name].dropna().to_numpy()
            counts, edges = np.histogram(values, bins=10)
            stats[name] = {
                "mean": float(values.mean()),
                "std": float(values.std()),
                "median": float(np.median(values)),
                "p01": float(np.quantile(values, 0.01)),
                "p99": float(np.quantile(values, 0.99)),
                "hist_edges": [float(item) for item in edges],
                "hist_share": [float(item) for item in counts / max(counts.sum(), 1)],
            }
        return stats

    def score(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        if self.pipeline is None:
            raise RuntimeError("Model is not fitted")
        matrix = self._matrix(frame)
        scores = self.pipeline.decision_function(matrix)
        flags = self.pipeline.predict(matrix) == -1
        return scores, flags

    def explain(self, frame: pd.DataFrame, top_k: int = 3) -> list[dict]:
        matrix = self._matrix(frame)
        explanations = []
        for _, row in matrix.iterrows():
            deviations = []
            for name in self.feature_names:
                value = row[name]
                if pd.isna(value):
                    continue
                info = self.stats[name]
                spread = info["std"] or 1.0
                deviations.append(
                    {
                        "feature": name,
                        "value": float(value),
                        "expected_range": [info["p01"], info["p99"]],
                        "historical_mean": info["mean"],
                        "deviation_sigma": float((value - info["mean"]) / spread),
                    }
                )
            deviations.sort(key=lambda item: abs(item["deviation_sigma"]), reverse=True)
            explanations.append({"top_features": deviations[:top_k]})
        return explanations
