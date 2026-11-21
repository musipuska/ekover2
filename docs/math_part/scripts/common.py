import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
MATH_DIR = ROOT / "docs" / "math_part"
FIGURES = MATH_DIR / "figures"
RESULTS = MATH_DIR / "results"
DATASET = next((ROOT / "data" / "raw").glob("*/*water_potability.csv"))

PALETTE = {
    "blue": "#2b6cb0",
    "orange": "#dd6b20",
    "green": "#2f855a",
    "red": "#c53030",
    "gray": "#718096",
    "purple": "#6b46c1",
}

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.size": 10,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "bold",
    }
)


def normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def load_water() -> pd.DataFrame:
    frame = pd.read_csv(DATASET)
    frame.columns = [normalize(name) for name in frame.columns]
    return frame


def parameters(frame: pd.DataFrame) -> list[str]:
    return [name for name in frame.columns if name != "potability"]


def save_figure(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES / name, bbox_inches="tight")
    plt.close(fig)


def save_results(name: str, payload: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
