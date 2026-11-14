from pydantic import BaseModel, Field

class QualityRuleResult(BaseModel):
    rule: str
    rule_type: str | None = None
    column: str | None = None
    severity: str
    status: str
    quarantine: bool = False
    failed_rows: int | None = None
    observed_value: float | None = None
    expected: str | None = None
    message: str | None = None


class DatasetQuality(BaseModel):
    """Отчёт о качестве обработанного набора данных."""

    dataset_id: str
    batch_id: str
    bronze_rows: int
    silver_rows: int
    removed_duplicates: int
    null_cells_after_cleaning: int
    quality_status: str
    quality_score: float | None = None
    quarantined_rows: int = 0
    gate_reason: str | None = None
    checks_total: int | None = None
    checks_passed: int | None = None
    checks_failed: int | None = None
    checks_skipped: int | None = None
    results: list[QualityRuleResult] = Field(default_factory=list)


class BatchSummary(BaseModel):
    dataset_id: str
    batch_id: str
    status: str
    published_at: str | None = None
    row_count: int | None = None
    quality_status: str | None = None
    quality_score: float | None = None
