import numpy as np
import pandas as pd
from scipy import stats

import matplotlib.pyplot as plt

from common import PALETTE, load_water, parameters, save_figure, save_results


def tukey(values: np.ndarray, k: float = 1.5):
    q1, q3 = np.quantile(values, [0.25, 0.75])
    spread = q3 - q1
    return q1, q3, spread, q1 - k * spread, q3 + k * spread


def theory():
    q3 = stats.norm.ppf(0.75)
    spread = 2 * q3
    fence = q3 + 1.5 * spread
    tail = 2 * stats.norm.sf(fence)
    z3 = 2 * stats.norm.sf(3)
    return {
        "q3_std_normal": float(q3),
        "iqr_std_normal": float(spread),
        "fence_sigma": float(fence),
        "p_outside_tukey_normal": float(tail),
        "p_outside_3sigma_normal": float(z3),
        "mad_to_sigma": float(1 / stats.norm.ppf(0.75)),
    }


def main():
    frame = load_water()
    names = parameters(frame)
    rows = {}
    for name in names:
        values = frame[name].dropna().to_numpy()
        q1, q3, spread, low, high = tukey(values)
        mean, std = values.mean(), values.std(ddof=1)
        z = np.abs((values - mean) / std)
        rows[name] = {
            "n": int(len(values)),
            "null_count": int(frame[name].isna().sum()),
            "null_share": float(frame[name].isna().mean()),
            "mean": float(mean),
            "std": float(std),
            "min": float(values.min()),
            "q1": float(q1),
            "median": float(np.median(values)),
            "q3": float(q3),
            "max": float(values.max()),
            "iqr": float(spread),
            "fence_low": float(low),
            "fence_high": float(high),
            "tukey_outliers": int(((values < low) | (values > high)).sum()),
            "tukey_share": float(((values < low) | (values > high)).mean()),
            "z3_outliers": int((z > 3).sum()),
            "z3_share": float((z > 3).mean()),
            "skewness": float(stats.skew(values)),
            "excess_kurtosis": float(stats.kurtosis(values)),
            "dagostino_p": float(stats.normaltest(values).pvalue),
        }

    matrix = frame[names]
    pearson = matrix.corr(method="pearson")
    spearman = matrix.corr(method="spearman")
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pair = matrix[[a, b]].dropna()
            r = pearson.loc[a, b]
            n = len(pair)
            z = np.arctanh(r)
            se = 1 / np.sqrt(n - 3)
            low, high = np.tanh([z - 1.96 * se, z + 1.96 * se])
            t = r * np.sqrt((n - 2) / (1 - r * r))
            pairs.append(
                {
                    "a": a, "b": b, "n": int(n), "pearson": float(r), "spearman": float(spearman.loc[a, b]),
                    "ci_low": float(low), "ci_high": float(high), "t": float(t),
                    "p_value": float(2 * stats.t.sf(abs(t), n - 2)),
                }
            )
    pairs.sort(key=lambda item: -abs(item["pearson"]))

    save_results(
        "02_descriptive_outliers.json",
        {"theory": theory(), "parameters": rows, "top_pairs": pairs[:6], "n_pairs": len(pairs),
         "pairs_p_below_005": int(sum(item["p_value"] < 0.05 for item in pairs)),
         "max_abs_pearson": float(max(abs(item["pearson"]) for item in pairs))},
    )

    t = theory()
    x = np.linspace(-4.2, 4.2, 600)
    pdf = stats.norm.pdf(x)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4))
    axes[0].plot(x, pdf, color=PALETTE["blue"])
    axes[0].fill_between(x, pdf, where=(x <= -t["fence_sigma"]) | (x >= t["fence_sigma"]), color=PALETTE["red"], alpha=0.6, label=f"хвосты: {t['p_outside_tukey_normal']*100:.3f}%")
    axes[0].axvline(-t["q3_std_normal"], color=PALETTE["gray"], linestyle="--")
    axes[0].axvline(t["q3_std_normal"], color=PALETTE["gray"], linestyle="--", label="Q1, Q3 = ±0.6745σ")
    axes[0].axvline(t["fence_sigma"], color=PALETTE["red"], linestyle=":")
    axes[0].axvline(-t["fence_sigma"], color=PALETTE["red"], linestyle=":", label=f"границы Тьюки ±{t['fence_sigma']:.3f}σ")
    axes[0].set_title("Правило 1.5·IQR для нормального закона")
    axes[0].set_xlabel("z")
    axes[0].legend(fontsize=8)
    ks = np.linspace(0.5, 4, 200)
    share = [2 * stats.norm.sf(t["q3_std_normal"] + k * 2 * t["q3_std_normal"]) for k in ks]
    axes[1].plot(ks, np.array(share) * 100, color=PALETTE["orange"])
    axes[1].axvline(1.5, color=PALETTE["gray"], linestyle="--")
    axes[1].axvline(3, color=PALETTE["gray"], linestyle=":")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("множитель k в границах Q ± k·IQR")
    axes[1].set_ylabel("доля «выбросов» при N(0,1), %")
    axes[1].set_title("Чувствительность правила Тьюки к k")
    save_figure(fig, "03_tukey_theory.png")

    fig, axes = plt.subplots(3, 3, figsize=(12, 9))
    for ax, name in zip(axes.ravel(), names):
        values = frame[name].dropna().to_numpy()
        info = rows[name]
        ax.hist(values, bins=40, color=PALETTE["blue"], alpha=0.8)
        ax.axvline(info["fence_low"], color=PALETTE["red"], linestyle="--")
        ax.axvline(info["fence_high"], color=PALETTE["red"], linestyle="--")
        ax.set_title(f"{name}: выбросов {info['tukey_outliers']} ({info['tukey_share']*100:.1f}%)", fontsize=9)
        ax.set_yticks([])
    save_figure(fig, "03_parameter_distributions.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, matrix_, title in zip(axes, (pearson, spearman), ("Пирсон", "Спирмен")):
        image = ax.imshow(matrix_.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_xticks(range(len(names)))
        ax.set_yticks(range(len(names)))
        ax.set_xticklabels(names, rotation=60, ha="right", fontsize=8)
        ax.set_yticklabels(names, fontsize=8)
        ax.set_title(f"Корреляции ({title})")
        ax.grid(False)
        fig.colorbar(image, ax=ax, fraction=0.046)
    save_figure(fig, "03_correlations.png")
    print(theory())
    print({k: (v["tukey_outliers"], v["z3_outliers"], round(v["skewness"], 2)) for k, v in rows.items()})
    print(pairs[:3])


if __name__ == "__main__":
    main()
