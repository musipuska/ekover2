import numpy as np
from scipy import special
from sklearn.ensemble import IsolationForest
from sklearn.ensemble._iforest import _average_path_length

import matplotlib.pyplot as plt

from common import PALETTE, load_water, parameters, save_figure, save_results

EULER = 0.5772156649015329


def c_exact(n: int) -> float:
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    return 2.0 * (special.digamma(n) + EULER) - 2.0 * (n - 1) / n


def c_asymptotic(n: int) -> float:
    return 2.0 * (np.log(n - 1) + EULER) - 2.0 * (n - 1) / n


def itree_leaf_depths(points: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    depths = np.zeros(len(points))
    stack = [(np.arange(len(points)), 0)]
    while stack:
        index, depth = stack.pop()
        if len(index) <= 1:
            depths[index] = depth
            continue
        values = points[index]
        low, high = values.min(), values.max()
        split = rng.uniform(low, high)
        left = values < split
        stack.append((index[left], depth + 1))
        stack.append((index[~left], depth + 1))
    return depths


def simulate_c(sizes, trials, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for n in sizes:
        means = []
        for _ in range(trials):
            points = rng.uniform(0, 1, n)
            means.append(itree_leaf_depths(points, rng).mean())
        rows.append((n, float(np.mean(means)), float(np.std(means) / np.sqrt(trials))))
    return rows


def manual_scores(model: IsolationForest, data: np.ndarray) -> np.ndarray:
    total = np.zeros(len(data))
    for tree, features in zip(model.estimators_, model.estimators_features_):
        subset = data[:, features]
        leaves = tree.apply(subset)
        depths = tree.tree_.compute_node_depths()[leaves]
        total += depths - 1.0 + _average_path_length(tree.tree_.n_node_samples[leaves])
    mean_depth = total / len(model.estimators_)
    return -(2.0 ** (-mean_depth / _average_path_length([model.max_samples_])[0]))


def main():
    sizes = [2, 3, 4, 8, 16, 32, 64, 128, 256, 512]
    simulated = simulate_c(sizes, trials=400)
    table = [
        {"n": n, "simulated": m, "se": se, "c_exact": c_exact(n), "c_asymptotic": c_asymptotic(n) if n > 2 else None}
        for n, m, se in simulated
    ]

    frame = load_water()
    names = parameters(frame)
    data = frame[names].fillna(frame[names].median()).to_numpy()
    model = IsolationForest(n_estimators=200, contamination=0.02, random_state=42).fit(data)
    sklearn_scores = model.score_samples(data)
    mine = manual_scores(model, data)
    offset = float(model.offset_)
    flags = model.predict(data) == -1
    threshold_by_quantile = float(np.quantile(sklearn_scores, 0.02))
    verification = {
        "max_abs_diff_manual_vs_sklearn": float(np.max(np.abs(mine - sklearn_scores))),
        "max_samples": int(model.max_samples_),
        "c_psi": float(c_exact(model.max_samples_)),
        "c_psi_sklearn": float(_average_path_length([model.max_samples_])[0]),
        "offset": offset,
        "quantile_0_02_of_scores": threshold_by_quantile,
        "flagged": int(flags.sum()),
        "flagged_share": float(flags.mean()),
        "score_min": float(sklearn_scores.min()),
        "score_max": float(sklearn_scores.max()),
    }

    save_results("03_isolation_forest.json", {"c_table": table, "verification": verification})

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    grid = np.arange(2, 513)
    axes[0].plot(grid, [c_exact(n) for n in grid], color=PALETTE["blue"], label="c(n) = 2H(n−1) − 2(n−1)/n")
    axes[0].plot(grid, grid - 1, color=PALETTE["red"], linestyle="--", label="n − 1 (худший случай)")
    axes[0].errorbar([t["n"] for t in table], [t["simulated"] for t in table], yerr=[1.96 * t["se"] for t in table], fmt="o", color=PALETTE["orange"], label="симуляция iTree (95% ДИ)")
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("n")
    axes[0].set_ylabel("средняя длина пути")
    axes[0].set_title("Рост c(n) логарифмический")
    axes[0].legend(fontsize=8)

    ratio = np.linspace(0, 3, 300)
    axes[1].plot(ratio, 2.0 ** (-ratio), color=PALETTE["purple"])
    axes[1].axhline(0.5, color=PALETTE["gray"], linestyle=":")
    axes[1].axvline(1, color=PALETTE["gray"], linestyle=":")
    axes[1].annotate("E[h] = c(n) → s = 0.5", (1, 0.5), (1.4, 0.7), arrowprops={"arrowstyle": "->"})
    axes[1].set_xlabel("E[h(x)] / c(n)")
    axes[1].set_ylabel("s(x, n)")
    axes[1].set_title("Оценка аномальности")

    axes[2].scatter(sklearn_scores, mine, s=4, color=PALETTE["blue"])
    lims = [sklearn_scores.min(), sklearn_scores.max()]
    axes[2].plot(lims, lims, color=PALETTE["red"], linestyle="--")
    axes[2].set_xlabel("score_samples (sklearn)")
    axes[2].set_ylabel("оценка по формуле статьи")
    axes[2].set_title(f"Воспроизведение: max|Δ| = {verification['max_abs_diff_manual_vs_sklearn']:.1e}")
    save_figure(fig, "04_isolation_forest_theory.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].hist(sklearn_scores, bins=60, color=PALETTE["blue"], alpha=0.85)
    axes[0].axvline(offset, color=PALETTE["red"], linestyle="--", label=f"offset = {offset:.4f}\n(2%-квантиль оценок)")
    axes[0].set_xlabel("score_samples")
    axes[0].set_title("Распределение оценок на water_potability")
    axes[0].legend(fontsize=8)
    ix, iy = names.index("ph"), names.index("hardness")
    axes[1].scatter(data[~flags, ix], data[~flags, iy], s=4, color=PALETTE["gray"], alpha=0.5, label="норма")
    axes[1].scatter(data[flags, ix], data[flags, iy], s=14, color=PALETTE["red"], label="аномалия (2%)")
    axes[1].set_xlabel("ph")
    axes[1].set_ylabel("hardness")
    axes[1].set_title("Проекция помеченных аномалий")
    axes[1].legend(fontsize=8)
    save_figure(fig, "04_isolation_forest_real.png")
    print(verification)
    print([(t["n"], round(t["simulated"], 3), round(t["c_exact"], 3)) for t in table])


if __name__ == "__main__":
    main()
