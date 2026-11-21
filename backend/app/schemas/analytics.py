from pydantic import BaseModel, ConfigDict


class Payload(BaseModel):
    """Базовый контракт ответа: обязательные поля проверяются, вложенные детали проходят как есть."""

    model_config = ConfigDict(extra="allow")


class Delta(Payload):
    previous: int
    change: int
    change_pct: float | None = None


class Kpi(Payload):
    key: str
    label: str
    value: int | float | None = None
    unit: str
    description: str
    delta: Delta | None = None


class PlatformStatus(Payload):
    status: str
    reasons: list[str]


class ExecutiveSummary(Payload):
    generated_at: str
    kpis: list[Kpi]
    dataset_activity: list[dict]
    processing_activity: list[dict]
    quality_distribution: dict[str, int]
    anomaly_overview: dict
    recent: dict
    platform_status: PlatformStatus


# --- Water quality ---------------------------------------------------------

class WaterCatalog(Payload):
    dataset_id: str
    batch_id: str
    parameters: list[str]
    stations: list[str]
    has_station: bool
    has_timestamp: bool
    row_count: int | None = None
    period_start: str | None = None
    period_end: str | None = None


class Distribution(Payload):
    dataset_id: str
    batch_id: str
    parameter: str
    rows_in_scope: int
    n: int
    null_count: int
    summary: dict | None = None
    percentiles: dict | None = None
    histogram: dict | None = None
    boxplot: dict | None = None
    threshold: dict | None = None


class Correlation(Payload):
    dataset_id: str
    batch_id: str
    method: str
    min_periods: int
    parameters: list[str]
    matrix: list[list[float | None]]
    pair_counts: list[list[int]]
    truncated: bool
    note: str


class Thresholds(Payload):
    items: list[dict]
    regulatory_norms_configured: bool


class Measurements(Payload):
    items: list[dict]
    total: int
    parameter: str
    dataset_id: str
    batch_id: str


# --- Data quality ------------------------------------------------------------

class QualityOverview(Payload):
    scope: str
    kpis: dict
    status_distribution: dict[str, int]
    status_distribution_all_batches: dict[str, int]
    trend: list[dict]
    ranking: list[dict]
    layers: list[dict]


class QualityRules(Payload):
    items: list[dict]
    total: int
    summary: dict


class QualityColumns(Payload):
    dataset_id: str
    row_count: int | None = None
    columns: list[dict]
    problem_columns: list[dict]
    null_history: list[dict]


# --- ML ----------------------------------------------------------------------

class MlOverview(Payload):
    rows_scored: int
    anomalies: int
    normal: int
    anomaly_rate: float | None = None
    models_used: list[dict]
    last_detection_at: str | None = None
    last_run: dict | None = None
    registry: dict
    score_note: str


class AnomaliesSummary(Payload):
    model: dict | None = None
    rows_scored: int
    anomalies: int
    by_station: list[dict]
    by_batch: list[dict]
    score_histogram: dict | None = None
    by_feature: list[dict]
    score_note: str


class AnomalySeries(Payload):
    dataset_id: str
    batch_id: str
    parameter: str
    model: dict
    x_kind: str
    normal: list[dict]
    anomalies: list[dict]
    total_points: int
    downsampled: bool


class AnomalyScatter(Payload):
    dataset_id: str
    batch_id: str
    parameter_x: str
    parameter_y: str
    model: dict
    normal: list[dict]
    anomalies: list[dict]
    total_points: int
    downsampled: bool


class AnomalyRecords(Payload):
    items: list[dict]
    total: int
    model: dict
    parameters: list[str]


class ModelDetail(Payload):
    model_name: str
    active_version: str | None = None
    versions: list[dict]
    detection_history: list[dict]


class MlRuns(Payload):
    items: list[dict]
    total: int


class Drift(Payload):
    available: bool
    thresholds: dict
    reports: list[dict]
    latest: dict | None = None


# --- Pipeline ----------------------------------------------------------------

class PipelineOverview(Payload):
    total_jobs: int
    by_status: dict[str, int]
    unknown_status_jobs: int
    success_rate: float | None = None
    avg_duration_seconds: float | None = None
    max_duration_seconds: float | None = None
    duration_sample_size: int
    last_execution: dict | None = None
    stage_status_counts: dict
    orchestration: dict


class PipelinePerformance(Payload):
    series: list[dict]
    stage_durations: list[dict]
    status_distribution: dict[str, int]


class JobsPage(Payload):
    items: list[dict]
    total: int


class JobDetail(Payload):
    job_id: str
    dataset_id: str
    dataset_name: str
    batch_id: str
    status: str | None = None
    metrics: dict
    lifecycle: list[dict]
    assets: list[dict]
    stage_timestamps_available: bool


class ErrorsPage(Payload):
    items: list[dict]
    total: int
    by_type: dict[str, int]
