import time

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve
from sklearn.neighbors import LocalOutlierFactor

import matplotlib.pyplot as plt

from experiments.anomaly_comparison import evaluate, iforest, iqr, lof, make_data, zscore
from common import PALETTE, save_figure, save_results

ROWS = 10000
SEEDS = 4
def lof_k(frame, k):
    return -LocalOutlierFactor(n_neighbors=k).fit(frame).negative_outlier_factor_


def standardized(frame):
    return (frame - frame.mean()) / frame.std()


METHODS = {
    "Z-score": lambda f, s: zscore(f),
    "IQR": lambda f, s: iqr(f),
    "Isolation Forest": iforest,
    "LOF": lambda f, s: lof(f),
    "LOF (стандартизация)": lambda f, s: lof(standardized(f)),
}
COLORS = {
    "Z-score": PALETTE["gray"],
    "IQR": PALETTE["orange"],
    "Isolation Forest": PALETTE["blue"],
    "LOF": PALETTE["green"],
    "LOF (стандартизация)": PALETTE["red"],
}


def make_shift(rows, rate, seed, amplitude):
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
    frame.loc[idx, "ph"] += rng.choice([-1, 1], len(idx)) * amplitude * 0.15
    frame.loc[idx, "turbidity"] += amplitude * 0.3
    return frame, labels


def make_correlated(rows, rate, seed, rho=0.9):
    rng = np.random.default_rng(seed)
    x1 = rng.standard_normal(rows)
    noise = rng.standard_normal(rows)
    x2 = rho * x1 + np.sqrt(1 - rho**2) * noise
    labels = np.zeros(rows, dtype=int)
    idx = rng.choice(rows, int(rows * rate), replace=False)
    labels[idx] = 1
    x2[idx] = -rho * x1[idx] + np.sqrt(1 - rho**2) * noise[idx]
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": rng.standard_normal(rows)})
    return frame, labels


def run(maker, rate, seeds, **kwargs):
    out = {name: {"roc_auc": [], "pr_auc": [], "f1": []} for name in METHODS}
    for seed in range(seeds):
        frame, labels = maker(ROWS, rate, seed, **kwargs)
        for name, method in METHODS.items():
            metrics = evaluate(method(frame, seed), labels, rate)
            for key in out[name]:
                out[name][key].append(metrics[key])
    return {
        name: {key: {"mean": float(np.mean(v)), "std": float(np.std(v))} for key, v in metrics.items()}
        for name, metrics in out.items()
    }


def main():
    base = run(make_data, 0.02, SEEDS)

    amplitudes = [0.5, 1, 1.5, 2, 3, 4, 6]
    amplitude_sweep = {a: run(make_shift, 0.02, 3, amplitude=a) for a in amplitudes}

    rates = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2]
    rate_sweep = {r: run(make_shift, r, 3, amplitude=3) for r in rates}

    correlated = run(make_correlated, 0.02, SEEDS)

    ks = [5, 10, 30, 100, 200, 300, 500, 1000]
    k_sweep = {}
    for k in ks:
        runs = []
        for seed in range(3):
            frame, labels = make_shift(ROWS, 0.02, seed, 3)
            scores = lof_k(standardized(frame), k)
            runs.append(evaluate(scores, labels, 0.02))
        k_sweep[k] = {m: {"mean": float(np.mean([r[m] for r in runs])), "std": float(np.std([r[m] for r in runs]))} for m in ("roc_auc", "pr_auc", "f1")}

    timing = {}
    for rows in (5000, 20000):
        frame, _ = make_data(rows, 0.02, 0)
        timing[rows] = {}
        for name, method in METHODS.items():
            start = time.perf_counter()
            method(frame, 0)
            timing[rows][name] = round(time.perf_counter() - start, 3)

    save_results(
        "05_detector_comparison.json",
        {
            "rows": ROWS,
            "seeds": SEEDS,
            "base": base,
            "amplitude_sweep": {str(k): v for k, v in amplitude_sweep.items()},
            "rate_sweep": {str(k): v for k, v in rate_sweep.items()},
            "correlated": correlated,
            "lof_k_sweep": {str(k): v for k, v in k_sweep.items()},
            "anomaly_count": int(ROWS * 0.02),
            "timing": {str(k): v for k, v in timing.items()},
        },
    )

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.3))
    for name in METHODS:
        axes[0].errorbar(amplitudes, [amplitude_sweep[a][name]["pr_auc"]["mean"] for a in amplitudes], yerr=[amplitude_sweep[a][name]["pr_auc"]["std"] for a in amplitudes], marker="o", color=COLORS[name], label=name)
        axes[1].errorbar(rates, [rate_sweep[r][name]["pr_auc"]["mean"] for r in rates], yerr=[rate_sweep[r][name]["pr_auc"]["std"] for r in rates], marker="o", color=COLORS[name], label=name)
    axes[0].set_xlabel("амплитуда сдвига в σ (pH и мутность)")
    axes[0].set_ylabel("PR-AUC")
    axes[0].set_title("Чувствительность к силе аномалии")
    axes[0].legend(fontsize=8)
    axes[1].set_xscale("log")
    axes[1].set_xlabel("доля аномалий в данных")
    axes[1].set_ylabel("PR-AUC")
    axes[1].set_title("Устойчивость к росту доли аномалий (амплитуда 3σ)")
    width = 0.16
    metrics_names = ["roc_auc", "pr_auc", "f1"]
    for i, name in enumerate(METHODS):
        axes[2].bar(np.arange(3) + i * width, [correlated[name][m]["mean"] for m in metrics_names], width, yerr=[correlated[name][m]["std"] for m in metrics_names], color=COLORS[name], label=name)
    axes[2].set_xticks(np.arange(3) + 2 * width)
    axes[2].set_xticklabels(["ROC-AUC", "PR-AUC", "F1"])
    axes[2].set_title("Нарушение корреляции (ρ = 0.9), маргинальные законы целы")
    axes[2].legend(fontsize=8)
    save_figure(fig, "05_detector_comparison.png")

    fig, ax = plt.subplots(figsize=(5.8, 4.4))
    ax.errorbar(ks, [k_sweep[k]["pr_auc"]["mean"] for k in ks], yerr=[k_sweep[k]["pr_auc"]["std"] for k in ks], marker="o", color=PALETTE["red"], label="PR-AUC")
    ax.errorbar(ks, [k_sweep[k]["roc_auc"]["mean"] for k in ks], yerr=[k_sweep[k]["roc_auc"]["std"] for k in ks], marker="s", color=PALETTE["blue"], label="ROC-AUC")
    ax.axvline(int(ROWS * 0.02), color=PALETTE["gray"], linestyle="--", label="число аномалий (200)")
    ax.set_xscale("log")
    ax.set_xlabel("число соседей k")
    ax.set_title("LOF: k должно превышать размер группы аномалий")
    ax.legend(fontsize=8)
    save_figure(fig, "05_lof_k_sweep.png")

    fig, ax = plt.subplots(figsize=(5.8, 4.6))
    frame, labels = make_shift(ROWS, 0.02, 0, 2)
    for name, method in METHODS.items():
        fpr, tpr, _ = roc_curve(labels, method(frame, 0))
        ax.plot(fpr, tpr, color=COLORS[name], label=name)
    ax.plot([0, 1], [0, 1], color=PALETTE["gray"], linestyle=":")
    ax.set_xlabel("FPR")
    ax.set_ylabel("TPR")
    ax.set_title("ROC-кривые, амплитуда 2σ, доля 2%")
    ax.legend(fontsize=8)
    save_figure(fig, "05_roc_curves.png")

    print({n: {k: round(v["mean"], 4) for k, v in m.items()} for n, m in base.items()})
    print({a: {n: round(m["pr_auc"]["mean"], 3) for n, m in v.items()} for a, v in amplitude_sweep.items()})
    print({r: {n: round(m["pr_auc"]["mean"], 3) for n, m in v.items()} for r, v in rate_sweep.items()})
    print({n: {k: round(v["mean"], 3) for k, v in m.items()} for n, m in correlated.items()})
    print({k: {m: round(v["mean"], 3) for m, v in r.items()} for k, r in k_sweep.items()})
    print(timing)


if __name__ == "__main__":
    main()
