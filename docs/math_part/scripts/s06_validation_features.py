import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score

import matplotlib.pyplot as plt

from backend.ml.evaluation import temporal_split
from backend.ml.features import FeatureConfig, build_features
from common import PALETTE, save_figure, save_results


def auc_identity(rng):
    rows = []
    for n_pos, n_neg in ((50, 950), (200, 800), (500, 500)):
        pos = rng.normal(1.0, 1.0, n_pos)
        neg = rng.normal(0.0, 1.0, n_neg)
        scores = np.concatenate([pos, neg])
        labels = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])
        pairs = (pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()
        u = stats.mannwhitneyu(pos, neg).statistic / (n_pos * n_neg)
        rows.append({"n_pos": n_pos, "n_neg": n_neg, "sklearn": float(roc_auc_score(labels, scores)), "pairs": float(pairs), "mannwhitney_u": float(u)})
    return rows


def precision_recall_identity(rng):
    rows = []
    for prevalence in (0.01, 0.02, 0.05, 0.1):
        n = 20000
        labels = np.zeros(n, dtype=int)
        positives = int(n * prevalence)
        labels[rng.choice(n, positives, replace=False)] = 1
        scores = rng.normal(0, 1, n) + 2.0 * labels
        flagged = np.zeros(n, dtype=bool)
        flagged[np.argsort(-scores)[:positives]] = True
        rows.append(
            {
                "prevalence": prevalence,
                "precision": float(precision_score(labels, flagged)),
                "recall": float(recall_score(labels, flagged)),
                "f1": float(f1_score(labels, flagged)),
                "pr_auc": float(average_precision_score(labels, scores)),
            }
        )
    return rows


def make_series(rng, length=600, window=24):
    time = pd.date_range("2026-01-01", periods=length, freq="h", tz="UTC")
    base = 7.2 + 0.2 * np.sin(np.arange(length) * 2 * np.pi / 24) + rng.normal(0, 0.05, length)
    return pd.DataFrame({"station": "S1", "measured_at": time, "ph": base, "turbidity": np.abs(rng.normal(1, 0.2, length))})


def causality_test(rng):
    frame = make_series(rng)
    config = FeatureConfig(timestamp_column="measured_at", station_column="station", rolling_window=24, min_periods=3)
    features, names = build_features(frame, config)
    t0 = 300
    changed = frame.copy()
    changed.loc[changed.index[t0]:, "ph"] += 5.0
    features_changed, _ = build_features(changed, config)

    def max_diff(columns, rows):
        return float(np.nanmax(np.abs(features.loc[rows, columns].to_numpy() - features_changed.loc[rows, columns].to_numpy())))

    before = features.index[:t0]
    at_t0 = features.index[[t0]]
    after = features.index[t0 + 1:t0 + 25]
    window = 24
    x = frame["ph"].to_numpy()
    previous_mean = pd.Series(x).shift(1).rolling(window, min_periods=3).mean().to_numpy()
    including_mean = pd.Series(x).rolling(window, min_periods=3).mean().to_numpy()
    dev_previous = x - previous_mean
    dev_including = x - including_mean
    previous_23 = pd.Series(x).shift(1).rolling(window - 1, min_periods=3).mean().to_numpy()
    ratios = dev_including[100:] / (x - previous_23)[100:]
    return {
        "max_diff_rows_before_t0": max_diff(["ph_roll_mean", "ph_roll_std", "ph_dev"], before),
        "max_diff_roll_mean_at_t0": max_diff(["ph_roll_mean", "ph_roll_std"], at_t0),
        "diff_dev_at_t0": max_diff(["ph_dev"], at_t0),
        "diff_roll_mean_after_t0": max_diff(["ph_roll_mean"], after),
        "feature_names": names,
        "ratio_dev_including_vs_previous_min": float(np.nanmin(ratios)),
        "ratio_dev_including_vs_previous_max": float(np.nanmax(ratios)),
        "theory_ratio_including_window": float((window - 1) / window),
    }


def spike_detection(rng):
    out = {}
    for label, shift in (("shift(1): окно из прошлого", 1), ("окно включает текущее", 0)):
        scores, labels = [], []
        for _ in range(30):
            frame = make_series(rng)
            positions = rng.choice(np.arange(60, 580), 12, replace=False)
            y = np.zeros(len(frame), dtype=int)
            y[positions] = 1
            series = frame["ph"].to_numpy().copy()
            series[positions] += 0.5
            s = pd.Series(series)
            mean = s.shift(shift).rolling(24, min_periods=3).mean()
            std = s.shift(shift).rolling(24, min_periods=3).std()
            z = ((s - mean) / std).abs().to_numpy()
            ok = ~np.isnan(z)
            scores.append(z[ok])
            labels.append(y[ok])
        out[label] = float(roc_auc_score(np.concatenate(labels), np.concatenate(scores)))
    return out


def sensitivity_check(rng, repeats=60):
    levels = (0.01, 0.02, 0.05)
    clean = {q: [] for q in levels}
    drift = {q: [] for q in levels}
    for _ in range(repeats):
        train = rng.standard_normal((6000, 3))
        test_same = rng.standard_normal((2000, 3))
        test_shift = rng.standard_normal((2000, 3)) + np.array([0.7, 0, 0])
        model = IsolationForest(n_estimators=100, random_state=int(rng.integers(1e6))).fit(train)
        base = model.score_samples(train)
        for q in levels:
            cut = np.quantile(base, q)
            clean[q].append(float(np.mean(model.score_samples(test_same) <= cut)))
            drift[q].append(float(np.mean(model.score_samples(test_shift) <= cut)))
    return {
        str(q): {
            "clean_mean": float(np.mean(clean[q])),
            "clean_std": float(np.std(clean[q])),
            "binomial_std": float(np.sqrt(q * (1 - q) / 2000)),
            "drift_mean": float(np.mean(drift[q])),
        }
        for q in levels
    }


def split_example():
    stamps = pd.to_datetime(["2026-01-01"] * 4 + ["2026-01-02"] * 4 + ["2026-01-03"] * 2, utc=True)
    frame = pd.DataFrame({"ts": stamps, "x": range(10)})
    train, test = temporal_split(frame, "ts", 0.7)
    return {"n": 10, "train_fraction": 0.7, "train_rows": len(train), "test_rows": len(test), "boundary": str(train["ts"].max())}


def main():
    rng = np.random.default_rng(2026)
    results = {
        "auc_identity": auc_identity(rng),
        "precision_recall_identity": precision_recall_identity(rng),
        "causality": causality_test(rng),
        "spike_detection_auc": spike_detection(rng),
        "sensitivity": sensitivity_check(rng),
        "split_example": split_example(),
    }
    save_results("06_validation_features.json", results)

    frame = make_series(np.random.default_rng(5))
    x = frame["ph"].copy()
    x.iloc[300] += 0.6
    previous = x.shift(1).rolling(24, min_periods=3)
    including = x.rolling(24, min_periods=3)
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.2))
    window = slice(270, 340)
    axes[0].plot(x.index[window], x.iloc[window], color=PALETTE["gray"], label="ph")
    axes[0].plot(x.index[window], previous.mean().iloc[window], color=PALETTE["blue"], label="среднее по прошлым 24 (shift(1))")
    axes[0].plot(x.index[window], including.mean().iloc[window], color=PALETTE["red"], linestyle="--", label="среднее с текущей точкой")
    axes[0].set_title("Скользящее среднее: причинное и нет")
    axes[0].legend(fontsize=7.5)
    dev_prev = (x - previous.mean()).iloc[window]
    dev_inc = (x - including.mean()).iloc[window]
    axes[1].plot(dev_prev.index, dev_prev, color=PALETTE["blue"], label="x − m(t−1)")
    axes[1].plot(dev_inc.index, dev_inc, color=PALETTE["red"], linestyle="--", label="x − m_с текущей")
    axes[1].set_title("Признак *_dev: скачок занижен в (w−1)/w")
    axes[1].legend(fontsize=8)
    levels = list(results["sensitivity"].keys())
    xpos = np.arange(len(levels))
    axes[2].bar(xpos - 0.2, [results["sensitivity"][q]["clean_mean"] for q in levels], 0.4, yerr=[1.96 * results["sensitivity"][q]["clean_std"] for q in levels], color=PALETTE["blue"], label="без дрейфа")
    axes[2].bar(xpos + 0.2, [results["sensitivity"][q]["drift_mean"] for q in levels], 0.4, color=PALETTE["red"], label="сдвиг 0.7σ")
    axes[2].plot(xpos - 0.2, [float(q) for q in levels], "k_", markersize=18, label="ожидание q")
    axes[2].set_xticks(xpos)
    axes[2].set_xticklabels([f"q = {q}" for q in levels])
    axes[2].set_title("contamination_sensitivity")
    axes[2].legend(fontsize=8)
    save_figure(fig, "06_features_and_sensitivity.png")

    print(json_safe(results))


def json_safe(results):
    import json
    return json.dumps(results, ensure_ascii=False, default=float)[:3500]


if __name__ == "__main__":
    main()
