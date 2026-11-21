import numpy as np
import pandas as pd

from backend.etl.quality.gate import critical_failures, evaluate_gate, quality_score, rule_coverage
from common import PALETTE, load_water, save_figure, save_results

import matplotlib.pyplot as plt


def rule_row(name, rule, severity, status, failed=0, observed=None):
    return {
        "rule": name,
        "rule_type": rule,
        "severity": severity,
        "status": status,
        "failed_rows": failed,
        "observed_value": observed,
    }


def evaluate_water(frame: pd.DataFrame) -> list[dict]:
    total = len(frame)
    results = [rule_row("dataset_not_empty", "min_rows", "critical", "passed" if total >= 1 else "failed", 0, total)]

    def between(name, column, low, high):
        values = pd.to_numeric(frame[column], errors="coerce")
        invalid = values.notna() & ((values < low) | ((values > high) if high is not None else False))
        failed = int(invalid.sum())
        return rule_row(name, "between", "warning", "failed" if failed else "passed", failed, failed)

    results.append(between("ph_physical_range", "ph", 0, 14))
    results.append(between("hardness_non_negative", "hardness", 0, None))
    results.append(between("turbidity_non_negative", "turbidity", 0, None))
    results.append(between("conductivity_non_negative", "conductivity", 0, None))
    results.append(rule_row("temperature_physical_range", "between", "warning", "skipped", None))
    ratio = float(frame["ph"].isna().mean())
    results.append(
        rule_row("ph_null_ratio", "max_null_ratio", "warning", "failed" if ratio > 0.5 else "passed", int(frame["ph"].isna().sum()), round(ratio, 6))
    )
    results.append(rule_row("measured_at_not_in_future", "not_in_future", "warning", "skipped", None))
    return results


def scenario(total, failed_warning, skipped, critical=0):
    results = []
    for index in range(total):
        if index < critical:
            results.append({"status": "failed", "severity": "critical"})
        elif index < critical + failed_warning:
            results.append({"status": "failed", "severity": "warning"})
        elif index < critical + failed_warning + skipped:
            results.append({"status": "skipped", "severity": "warning"})
        else:
            results.append({"status": "passed", "severity": "warning"})
    return results


def main():
    frame = load_water()
    results = evaluate_water(frame)
    summary = {
        "rows": len(frame),
        "rules_total": len(results),
        "passed": sum(item["status"] == "passed" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "skipped": sum(item["status"] == "skipped" for item in results),
        "quality_score": quality_score(results),
        "rule_coverage": rule_coverage(results),
        "critical_failures": critical_failures(results),
        "gate": evaluate_gate(results),
        "ph_null_ratio": float(frame["ph"].isna().mean()),
        "null_cells": int(frame.drop(columns="potability").isna().sum().sum()),
        "null_cells_by_column": {k: int(v) for k, v in frame.isna().sum().items() if v},
        "rules": results,
    }

    n = len(results)
    failed_axis = np.arange(0, n + 1)
    skipped_axis = np.arange(0, n + 1)
    grid = np.full((n + 1, n + 1), np.nan)
    for f in failed_axis:
        for s in skipped_axis:
            if f + s <= n:
                grid[f, s] = quality_score(scenario(n, f, s))
    summary["grid_n"] = n
    summary["grid_example"] = {"failed_warning=2,skipped=2": grid[2, 2], "failed_warning=0,skipped=2": grid[0, 2]}

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    image = axes[0].imshow(grid, origin="lower", cmap="Blues", vmin=0, vmax=1)
    axes[0].set_xlabel("число пропущенных правил s")
    axes[0].set_ylabel("число проваленных warning-правил f")
    axes[0].set_title(f"Quality score при n = {n}")
    axes[0].grid(False)
    for f in failed_axis:
        for s in skipped_axis:
            if not np.isnan(grid[f, s]):
                axes[0].text(s, f, f"{grid[f, s]:.2f}", ha="center", va="center", fontsize=6.5, color="black" if grid[f, s] < 0.65 else "white")
    fig.colorbar(image, ax=axes[0], fraction=0.046)

    coverage = [rule_coverage(scenario(n, 0, s)) for s in skipped_axis]
    score_no_fail = [quality_score(scenario(n, 0, s)) for s in skipped_axis]
    score_one_critical = [quality_score(scenario(n, 0, min(s, n - 1), critical=1)) for s in skipped_axis]
    axes[1].plot(skipped_axis, coverage, "o-", color=PALETTE["blue"], label="rule coverage")
    axes[1].plot(skipped_axis, score_no_fail, "s--", color=PALETTE["green"], label="quality score (нет провалов)")
    axes[1].plot(skipped_axis, score_one_critical, "^-", color=PALETTE["red"], label="quality score (1 critical)")
    axes[1].axvline(2, color=PALETTE["gray"], linestyle=":")
    axes[1].annotate("реальный набор:\ns = 2 → 0.75", (2, 0.75), (3.2, 0.9), arrowprops={"arrowstyle": "->"})
    axes[1].set_xlabel("число пропущенных правил s")
    axes[1].set_ylabel("значение")
    axes[1].set_title("Пропуск правила снижает score и coverage")
    axes[1].legend(loc="lower left")
    save_figure(fig, "01_quality_score_surface.png")

    save_results("01_quality_score.json", summary)
    print({k: v for k, v in summary.items() if k not in {"rules", "grid_example"}})


if __name__ == "__main__":
    main()
