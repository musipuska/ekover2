import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "default.yaml"


@dataclass
class RuleSpec:
    name: str
    rule: str
    severity: str = "warning"
    column: str | None = None
    columns: list[str] | None = None
    min: float | None = None
    max: float | None = None
    values: list | None = None
    threshold: float | None = None
    pattern: str | None = None
    quarantine: bool = False


@dataclass
class PipelineConfig:
    dataset: str = "default"
    business_key: list[str] = field(default_factory=list)
    timestamp_columns: list[str] = field(default_factory=list)
    required_columns: list[str] = field(default_factory=list)
    rules: list[RuleSpec] = field(default_factory=list)
    allow_warning_downstream: bool = True
    # auto | none | business_key | full_row | record_hash
    dedup_strategy: str = "auto"


DEDUP_STRATEGIES = {"auto", "none", "business_key", "full_row", "record_hash"}


def parse_config(payload: dict) -> PipelineConfig:
    rules = [RuleSpec(**item) for item in payload.get("rules", [])]
    strategy = payload.get("dedup_strategy", "auto")
    if strategy not in DEDUP_STRATEGIES:
        raise ValueError(f"Неизвестная dedup_strategy: {strategy}")
    return PipelineConfig(
        dataset=payload.get("dataset", "default"),
        business_key=list(payload.get("business_key", [])),
        timestamp_columns=list(payload.get("timestamp_columns", [])),
        required_columns=list(payload.get("required_columns", [])),
        rules=rules,
        allow_warning_downstream=bool(payload.get("allow_warning_downstream", True)),
        dedup_strategy=strategy,
    )


def load_pipeline_config(path: str | Path | None = None) -> PipelineConfig:
    target = Path(path or os.getenv("ETL_CONFIG_PATH") or DEFAULT_CONFIG_PATH)
    if not target.is_file():
        return PipelineConfig()
    with target.open("r", encoding="utf-8") as file:
        return parse_config(yaml.safe_load(file) or {})
