import runpy
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[2]

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

ORDER = [
    "s01_quality_score",
    "s02_descriptive_outliers",
    "s03_isolation_forest",
    "s04_psi",
    "s05_detector_comparison",
    "s06_validation_features",
    "s07_real_data",
]


def main():
    selected = sys.argv[1:] or ORDER
    for name in selected:
        start = time.perf_counter()
        module = runpy.run_path(str(SCRIPTS / f"{name}.py"), run_name=name)
        module["main"]()
        print(f"{name}: {time.perf_counter() - start:.1f} s", file=sys.stderr)


if __name__ == "__main__":
    main()
