import numpy as np
import pandas as pd

import matplotlib.pyplot as plt

from backend.ml.anomaly_detection import detect_anomalies
from common import PALETTE, load_water, parameters, save_figure, save_results


def main():
    frame = load_water()
    names = parameters(frame)
    features = frame[names]

    flagged = detect_anomalies(features, contamination=0.02, random_state=42)
    is_anomaly = flagged["is_anomaly"].to_numpy()
    score = flagged["anomaly_score"].to_numpy()

    q1, q3 = features.quantile(0.25), features.quantile(0.75)
    spread = q3 - q1
    tukey_hits = ((features < q1 - 1.5 * spread) | (features > q3 + 1.5 * spread))
    tukey_any = tukey_hits.any(axis=1).to_numpy()
    tukey_count = tukey_hits.sum(axis=1).to_numpy()
    z = ((features - features.mean()) / features.std()).abs()
    z_any = (z > 3).any(axis=1).to_numpy()
    has_null = features.isna().any(axis=1).to_numpy()

    def overlap(a, b):
        inter = int((a & b).sum())
        union = int((a | b).sum())
        return {"a": int(a.sum()), "b": int(b.sum()), "intersection": inter, "jaccard": inter / union if union else 0.0}

    median_filled = features.fillna(features.median())
    deviation = ((median_filled - median_filled.median()) / median_filled.std()).abs()
    dominant = deviation[is_anomaly].idxmax(axis=1).value_counts().to_dict()

    rates = {}
    for label, mask in (("с пропусками", has_null), ("без пропусков", ~has_null)):
        rates[label] = {"rows": int(mask.sum()), "flagged": int(is_anomaly[mask].sum()), "share": float(is_anomaly[mask].mean())}

    stability = []
    base_flags = is_anomaly
    for seed in range(1, 11):
        other = detect_anomalies(features, contamination=0.02, random_state=seed)["is_anomaly"].to_numpy()
        stability.append(overlap(base_flags, other)["jaccard"])

    contamination_grid = {}
    for c in (0.005, 0.01, 0.02, 0.05, 0.1):
        out = detect_anomalies(features, contamination=c, random_state=42)
        contamination_grid[str(c)] = {"flagged": int(out["is_anomaly"].sum()), "threshold_score": float(out.loc[out["is_anomaly"], "anomaly_score"].max())}

    result = {
        "rows": len(frame),
        "iforest_flagged": int(is_anomaly.sum()),
        "tukey_any_flagged": int(tukey_any.sum()),
        "z3_any_flagged": int(z_any.sum()),
        "rows_with_null": int(has_null.sum()),
        "iforest_vs_tukey": overlap(is_anomaly, tukey_any),
        "iforest_vs_z3": overlap(is_anomaly, z_any),
        "iforest_vs_tukey_2plus": overlap(is_anomaly, tukey_count >= 2),
        "dominant_parameter_of_flagged": dominant,
        "flag_rate_by_missingness": rates,
        "seed_stability_jaccard_mean": float(np.mean(stability)),
        "seed_stability_jaccard_min": float(np.min(stability)),
        "seed_stability_jaccard_max": float(np.max(stability)),
        "contamination_grid": contamination_grid,
        "mean_tukey_hits_flagged": float(tukey_count[is_anomaly].mean()),
        "mean_tukey_hits_normal": float(tukey_count[~is_anomaly].mean()),
        "mean_score_flagged": float(score[is_anomaly].mean()),
        "mean_score_normal": float(score[~is_anomaly].mean()),
    }
    save_results("07_real_data.json", result)

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.3))
    groups = [score[tukey_count == k] for k in range(0, int(tukey_count.max()) + 1) if (tukey_count == k).sum() > 5]
    labels = [str(k) for k in range(0, int(tukey_count.max()) + 1) if (tukey_count == k).sum() > 5]
    axes[0].boxplot(groups, tick_labels=labels, patch_artist=True, boxprops={"facecolor": PALETTE["blue"], "alpha": 0.5})
    axes[0].set_xlabel("число параметров вне границ Тьюки в строке")
    axes[0].set_ylabel("anomaly_score (ниже — аномальнее)")
    axes[0].set_title("Оценка IF растёт с числом выбросов по IQR")

    counts = pd.Series(dominant).reindex(names).fillna(0)
    axes[1].barh(counts.index, counts.values, color=PALETTE["orange"])
    axes[1].set_xlabel("число помеченных строк")
    axes[1].set_title("Параметр с максимальным |z| среди 66 аномалий")
    axes[1].invert_yaxis()

    axes[2].plot(list(map(float, contamination_grid)), [v["flagged"] for v in contamination_grid.values()], "o-", color=PALETTE["blue"], label="помечено")
    axes[2].plot(list(map(float, contamination_grid)), [c * len(frame) for c in map(float, contamination_grid)], "k--", label="c · n")
    axes[2].set_xscale("log")
    axes[2].set_yscale("log")
    axes[2].set_xlabel("contamination c")
    axes[2].set_ylabel("число аномалий")
    axes[2].set_title("Число флагов определяется параметром c")
    axes[2].legend(fontsize=8)
    save_figure(fig, "04_real_data_iforest.png")
    print({k: v for k, v in result.items() if k != "contamination_grid"})


if __name__ == "__main__":
    main()
