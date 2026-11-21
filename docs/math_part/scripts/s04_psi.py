import numpy as np
from scipy import stats

import matplotlib.pyplot as plt

from backend.ml.monitoring import EPSILON, PSI_ALERT, PSI_WARNING, population_stability_index
from common import PALETTE, load_water, parameters, save_figure, save_results

BINS = 10


def reference(values: np.ndarray):
    counts, edges = np.histogram(values, bins=BINS)
    return (counts / counts.sum()).tolist(), edges.tolist()


def psi_of(shares, edges, values):
    return population_stability_index(shares, edges, values)


def null_distribution(rng, n_train, n_batch, trials):
    out = np.empty(trials)
    for i in range(trials):
        train = rng.standard_normal(n_train)
        shares, edges = reference(train)
        out[i] = psi_of(shares, edges, rng.standard_normal(n_batch))
    return out


def shift_curve(rng, deltas, n_train, n_batch, trials, mode):
    means, low, high = [], [], []
    for delta in deltas:
        values = np.empty(trials)
        for i in range(trials):
            train = rng.standard_normal(n_train)
            shares, edges = reference(train)
            if mode == "location":
                batch = rng.standard_normal(n_batch) + delta
            else:
                batch = rng.standard_normal(n_batch) * (1 + delta)
            values[i] = psi_of(shares, edges, batch)
        means.append(values.mean())
        low.append(np.quantile(values, 0.05))
        high.append(np.quantile(values, 0.95))
    return np.array(means), np.array(low), np.array(high)


def population_psi(delta, edges):
    probabilities = np.diff(stats.norm.cdf(edges))
    inner = np.asarray(edges[1:-1])
    cuts = np.concatenate(([-np.inf], inner, [np.inf]))
    a = np.diff(stats.norm.cdf(cuts, loc=delta))
    e = np.diff(stats.norm.cdf(cuts))
    return float(np.sum((a - e) * np.log(a / e)))


def main():
    rng = np.random.default_rng(7)
    n_train = 5000
    batches = [50, 100, 200, 500, 1000, 2000, 5000]
    trials = 1500
    null_rows = []
    for n_batch in batches:
        sample = null_distribution(rng, n_train, n_batch, trials)
        theory = (BINS - 1) * (1 / n_batch + 1 / n_train)
        null_rows.append(
            {
                "n_batch": n_batch,
                "mean_psi": float(sample.mean()),
                "theory_mean": float(theory),
                "p_warning": float((sample >= PSI_WARNING).mean()),
                "p_alert": float((sample >= PSI_ALERT).mean()),
                "q95": float(np.quantile(sample, 0.95)),
            }
        )

    chi_quantile_95 = {
        n: float(stats.chi2.ppf(0.95, BINS - 1) * (1 / n + 1 / n_train)) for n in batches
    }

    deltas = np.linspace(0, 1.5, 16)
    loc_mean, loc_low, loc_high = shift_curve(rng, deltas, n_train, 2000, 300, "location")
    scale_deltas = np.linspace(0, 1.0, 11)
    scale_mean, scale_low, scale_high = shift_curve(rng, scale_deltas, n_train, 2000, 300, "scale")

    train_probe = rng.standard_normal(200000)
    _, edges_probe = reference(train_probe)
    population = [population_psi(d, edges_probe) for d in deltas]

    def crossing(curve, grid, level):
        for i in range(1, len(grid)):
            if curve[i] >= level:
                x0, x1, y0, y1 = grid[i - 1], grid[i], curve[i - 1], curve[i]
                return float(x0 + (level - y0) * (x1 - x0) / (y1 - y0))
        return None

    empty_bin = []
    for share in (0.2, 0.1, 0.05, 0.02, 0.01):
        term = (EPSILON - share) * np.log(EPSILON / share)
        empty_bin.append({"expected_share": share, "psi_contribution": float(term)})

    summary = {
        "bins": BINS,
        "epsilon": EPSILON,
        "n_train": n_train,
        "null": null_rows,
        "chi2_q95_scaled": chi_quantile_95,
        "delta_for_warning_sample": crossing(loc_mean, deltas, PSI_WARNING),
        "delta_for_alert_sample": crossing(loc_mean, deltas, PSI_ALERT),
        "delta_for_warning_population": crossing(population, deltas, PSI_WARNING),
        "delta_for_alert_population": crossing(population, deltas, PSI_ALERT),
        "delta_for_warning_continuous": float(np.sqrt(PSI_WARNING)),
        "delta_for_alert_continuous": float(np.sqrt(PSI_ALERT)),
        "empty_bin": empty_bin,
        "location": {"delta": deltas.tolist(), "mean": loc_mean.tolist(), "population": population},
        "scale": {"delta": scale_deltas.tolist(), "mean": scale_mean.tolist()},
    }

    frame = load_water()
    names = parameters(frame)
    half = len(frame) // 2
    real = {}
    for name in names:
        values = frame[name].dropna().to_numpy()
        cut = int(len(values) * 0.7)
        shares, edges = reference(values[:cut])
        value = psi_of(shares, edges, values[cut:])
        theory = (BINS - 1) * (1 / (len(values) - cut) + 1 / cut)
        permuted = np.empty(300)
        for i in range(300):
            shuffled = rng.permutation(values)
            ref_shares, ref_edges = reference(shuffled[:cut])
            permuted[i] = psi_of(ref_shares, ref_edges, shuffled[cut:])
        real[name] = {
            "psi_70_30": float(value),
            "chi2_expectation": float(theory),
            "permutation_mean": float(permuted.mean()),
            "permutation_q95": float(np.quantile(permuted, 0.95)),
            "permutation_p_value": float((np.sum(permuted >= value) + 1) / (len(permuted) + 1)),
            "n_test": int(len(values) - cut),
        }
    summary["real_data_70_30"] = real
    save_results("04_psi.json", summary)

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.3))
    axes[0].plot([r["n_batch"] for r in null_rows], [r["mean_psi"] for r in null_rows], "o-", color=PALETTE["blue"], label="симуляция E[PSI]")
    axes[0].plot([r["n_batch"] for r in null_rows], [r["theory_mean"] for r in null_rows], "s--", color=PALETTE["orange"], label="(B−1)(1/n_a + 1/n_e)")
    axes[0].axhline(PSI_WARNING, color=PALETTE["red"], linestyle=":", label="порог warning 0.1")
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("размер проверяемого пакета n_a")
    axes[0].set_ylabel("PSI без дрейфа")
    axes[0].set_title("Шумовой уровень PSI")
    axes[0].legend(fontsize=8)

    axes[1].plot([r["n_batch"] for r in null_rows], [r["p_warning"] * 100 for r in null_rows], "o-", color=PALETTE["orange"], label="P(PSI ≥ 0.1)")
    axes[1].plot([r["n_batch"] for r in null_rows], [r["p_alert"] * 100 for r in null_rows], "s-", color=PALETTE["red"], label="P(PSI ≥ 0.25)")
    axes[1].set_xscale("log")
    axes[1].set_xlabel("размер проверяемого пакета n_a")
    axes[1].set_ylabel("ложные срабатывания, %")
    axes[1].set_title("Ложные тревоги при отсутствии дрейфа")
    axes[1].legend(fontsize=8)

    axes[2].fill_between(deltas, loc_low, loc_high, color=PALETTE["blue"], alpha=0.2, label="90% диапазон (n_a = 2000)")
    axes[2].plot(deltas, loc_mean, "o-", color=PALETTE["blue"], label="выборочный PSI")
    axes[2].plot(deltas, population, "s--", color=PALETTE["green"], label="PSI на уровне распределений (10 бинов)")
    axes[2].plot(deltas, deltas**2, color=PALETTE["purple"], linestyle=":", label="J = δ² (без дискретизации)")
    axes[2].axhline(PSI_WARNING, color=PALETTE["gray"], linestyle=":")
    axes[2].axhline(PSI_ALERT, color=PALETTE["red"], linestyle=":")
    axes[2].set_ylim(0, 1.0)
    axes[2].set_xlabel("сдвиг среднего δ (в σ)")
    axes[2].set_ylabel("PSI")
    axes[2].set_title("Реакция PSI на сдвиг среднего")
    axes[2].legend(fontsize=7.5)
    save_figure(fig, "07_psi_behaviour.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    sample = null_distribution(np.random.default_rng(11), n_train, 200, 3000)
    axes[0].hist(sample, bins=50, density=True, color=PALETTE["blue"], alpha=0.8, label="симуляция, n_a = 200")
    scale = 1 / 200 + 1 / n_train
    grid = np.linspace(0.001, sample.max(), 400)
    axes[0].plot(grid, stats.chi2.pdf(grid / scale, BINS - 1) / scale, color=PALETTE["red"], label=f"scale · χ²({BINS - 1})")
    axes[0].axvline(PSI_WARNING, color=PALETTE["gray"], linestyle=":")
    axes[0].set_xlabel("PSI")
    axes[0].set_title("Распределение PSI без дрейфа ≈ масштабированное χ²")
    axes[0].legend(fontsize=8)

    ordered = sorted(real.items(), key=lambda item: -item[1]["psi_70_30"])
    axes[1].barh([name for name, _ in ordered], [info["psi_70_30"] for _, info in ordered], color=PALETTE["blue"], label="PSI(первые 70% → последние 30%)")
    axes[1].scatter([info["permutation_mean"] for _, info in ordered], range(len(ordered)), color=PALETTE["red"], zorder=3, label="среднее по 300 перестановкам строк")
    axes[1].scatter([info["permutation_q95"] for _, info in ordered], range(len(ordered)), color=PALETTE["orange"], marker="|", s=120, zorder=3, label="95%-квантиль перестановок")
    axes[1].axvline(PSI_WARNING, color=PALETTE["gray"], linestyle=":")
    axes[1].invert_yaxis()
    axes[1].set_xlabel("PSI")
    axes[1].set_title("water_potability: проверка на «нулевом» случае")
    axes[1].legend(fontsize=8)
    save_figure(fig, "07_psi_null_and_real.png")

    print([(r["n_batch"], round(r["mean_psi"], 4), round(r["theory_mean"], 4), r["p_warning"], r["p_alert"]) for r in null_rows])
    print({k: summary[k] for k in summary if k.startswith("delta_for")})
    print(empty_bin)
    print({k: (round(v["psi_70_30"], 4), round(v["permutation_mean"], 4), round(v["permutation_q95"], 4), round(v["permutation_p_value"], 3)) for k, v in real.items()})


if __name__ == "__main__":
    main()
