import argparse
import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.neighbors import LocalOutlierFactor


def make_data(rows, rate, seed):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {
            "ph": rng.normal(7.2, 0.15, rows),
            "temperature": rng.normal(15, 2, rows),
            "turbidity": np.abs(rng.normal(1, 0.3, rows)),
        }
    )
    labels = np.zeros(rows, dtype=int)
    idx = rng.choice(rows, int(rows * rate), replace=False)
    labels[idx] = 1
    frame.loc[idx, "ph"] += rng.choice([-1, 1], len(idx)) * rng.uniform(1.0, 2.5, len(idx))
    frame.loc[idx, "turbidity"] += rng.uniform(2, 6, len(idx))
    return frame, labels


def zscore(frame):
    return np.abs((frame - frame.mean()) / frame.std()).max(axis=1).to_numpy()


def iqr(frame):
    q1, q3 = frame.quantile(0.25), frame.quantile(0.75)
    spread = (q3 - q1).replace(0, 1e-9)
    distance = np.maximum((q1 - frame) / spread, (frame - q3) / spread).clip(lower=0)
    return distance.max(axis=1).to_numpy()


def iforest(frame, seed):
    return -IsolationForest(n_estimators=200, random_state=seed).fit(frame).score_samples(frame)


def lof(frame):
    return -LocalOutlierFactor(n_neighbors=30).fit(frame).negative_outlier_factor_


def evaluate(scores, labels, rate):
    threshold = np.quantile(scores, 1 - rate)
    return {
        "roc_auc": round(roc_auc_score(labels, scores), 4),
        "pr_auc": round(average_precision_score(labels, scores), 4),
        "f1": round(f1_score(labels, scores >= threshold), 4),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--rate", type=float, default=0.02)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--out", default="experiments/results_anomaly.json")
    args = parser.parse_args()

    methods = {
        "zscore": lambda f, s: zscore(f),
        "iqr": lambda f, s: iqr(f),
        "isolation_forest": iforest,
        "lof": lambda f, s: lof(f),
    }
    runs = {name: [] for name in methods}
    for seed in range(args.seeds):
        frame, labels = make_data(args.rows, args.rate, seed)
        for name, method in methods.items():
            start = time.perf_counter()
            metrics = evaluate(method(frame, seed), labels, args.rate)
            metrics["seconds"] = round(time.perf_counter() - start, 3)
            runs[name].append(metrics)

    summary = {
        name: {
            key: {"mean": round(float(np.mean([r[key] for r in items])), 4),
                  "std": round(float(np.std([r[key] for r in items])), 4)}
            for key in items[0]
        }
        for name, items in runs.items()
    }
    with open(args.out, "w", encoding="utf-8") as file:
        json.dump({"params": vars(args), "summary": summary}, file, ensure_ascii=False, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
