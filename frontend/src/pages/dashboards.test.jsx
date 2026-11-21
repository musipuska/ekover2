import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const names = [
    "summary", "martsDatasets", "trends", "stationMetrics", "waterCatalog", "distribution", "correlation", "thresholds",
    "measurements", "qualityOverview", "qualityRules", "qualityColumns", "mlOverview", "anomaliesSummary", "anomalySeries",
    "anomalyScatter", "anomalyRecords", "modelDetail", "mlRuns", "drift", "models", "pipelineOverview", "pipelinePerformance",
    "pipelineJobs", "pipelineJob", "pipelineErrors",
  ];
  return { analytics: Object.fromEntries(names.map((n) => [n, vi.fn()])), getDatasets: vi.fn() };
});

vi.mock("../services/analyticsApi", () => ({ analytics: mocks.analytics }));
vi.mock("../services/api", async (original) => ({ ...(await original()), api: { getDatasets: mocks.getDatasets } }));
vi.mock("../components/charts/EChart", () => ({
  default: ({ option, label }) => <div data-testid="chart" role="img" aria-label={label} data-first-series={JSON.stringify(option.series?.[0]?.data ?? null)} />,
}));

import DashboardProvider from "../context/DashboardProvider";
import DataQualityDashboard from "./DataQualityDashboard";
import MLAnalyticsDashboard from "./MLAnalyticsDashboard";
import OverviewDashboard from "./OverviewDashboard";
import PipelineDashboard from "./PipelineDashboard";
import WaterQualityDashboard from "./WaterQualityDashboard";

const A = mocks.analytics;
const ok = (data, meta = {}) => Promise.resolve({ data, meta: { generated_at: "2026-11-17T10:00:00+00:00", ...meta } });
const lastParams = (fn) => fn.mock.calls.at(-1)[0];

const DATASETS = [{ id: "ds-1", name: "Река Ока" }, { id: "ds-2", name: "Озеро" }];

function mount(page) {
  const navigate = vi.fn();
  render(<DashboardProvider navigate={navigate} navParams={{}}>{page}</DashboardProvider>);
  return navigate;
}

const kpi = (key, label, value, extra = {}) => ({ key, label, value, unit: "шт.", description: `${label} desc`, delta: null, ...extra });
const SUMMARY = {
  generated_at: "2026-11-17T10:00:00+00:00",
  kpis: [kpi("datasets", "Наборы данных", 3, { delta: { previous: 2, change: 1, change_pct: 50 } }), kpi("anomalies", "Аномалии", null)],
  dataset_activity: [{ date: "2026-11-01", datasets: 1 }],
  processing_activity: [], quality_distribution: { passed: 2, failed: 1 },
  anomaly_overview: { model: null, by_station: [], by_model: [] },
  recent: { datasets: [], jobs: [], quality_reports: [], errors: [] },
  platform_status: { status: "degraded", reasons: ["Есть наборы данных, не прошедшие quality gate"] },
};

beforeEach(() => {
  Object.values(A).forEach((fn) => fn.mockReset());
  mocks.getDatasets.mockReset().mockResolvedValue(DATASETS);
  A.martsDatasets.mockImplementation(() => ok([{ dataset_id: "ds-1", batch_id: "b1" }, { dataset_id: "ds-2", batch_id: "b2" }]));
  A.waterCatalog.mockImplementation(() => ok({ dataset_id: "ds-1", batch_id: "b1", parameters: ["ph", "temperature"], stations: ["s0", "s1"], has_station: true, has_timestamp: true }));
  A.trends.mockImplementation(() => ok([], { total: 0 }));
});

describe("OverviewDashboard", () => {
  it("renders real KPIs, N/A for missing values, delta and platform status", async () => {
    A.summary.mockImplementation(() => ok(SUMMARY));
    mount(<OverviewDashboard />);
    expect(await screen.findByText("Наборы данных")).toBeInTheDocument();
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(screen.getByText(/\+1 \(\+50%\)/)).toBeInTheDocument();
    expect(screen.getByText("Есть проблемы")).toBeInTheDocument();
    expect(screen.getByText(/Обновлено:/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Загрузка датасетов по дням" })).toBeInTheDocument();
    expect(screen.getByText("Processing Activity")).toBeInTheDocument();
  });

  it("shows an error with retry and recovers", async () => {
    A.summary.mockRejectedValueOnce(new Error("Сервер недоступен")).mockImplementation(() => ok(SUMMARY));
    mount(<OverviewDashboard />);
    const alerts = await screen.findAllByRole("alert");
    expect(alerts[0]).toHaveTextContent("Сервер недоступен");
    await userEvent.click(within(alerts[0]).getByRole("button", { name: /Повторить/ }));
    expect(await screen.findByText("Аномалии")).toBeInTheDocument();
    expect(A.summary).toHaveBeenCalledTimes(2);
  });

  it("dataset and period filters change the request, not just the label", async () => {
    A.summary.mockImplementation(() => ok(SUMMARY));
    mount(<OverviewDashboard />);
    await screen.findByText("Наборы данных");
    expect(lastParams(A.summary)).toMatchObject({ dataset_id: "", date_from: undefined, date_to: undefined });

    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Набор данных" }), "ds-2");
    await waitFor(() => expect(lastParams(A.summary)).toMatchObject({ dataset_id: "ds-2" }));

    await userEvent.type(screen.getByLabelText("С даты"), "2026-11-01");
    await waitFor(() => expect(lastParams(A.summary)).toMatchObject({ dataset_id: "ds-2", date_from: "2026-11-01" }));
  });

  it("shows empty states when the platform has no data", async () => {
    A.summary.mockImplementation(() => ok({
      ...SUMMARY, kpis: [kpi("datasets", "Наборы данных", 0)], dataset_activity: [], quality_distribution: {},
      platform_status: { status: "no_data", reasons: ["Нет данных за выбранный период"] },
    }));
    mount(<OverviewDashboard />);
    expect(await screen.findByText("За период нет загруженных наборов")).toBeInTheDocument();
    expect(screen.getByText("Отчётов качества пока нет")).toBeInTheDocument();
    const status = screen.getByText("Статус платформы").closest("section");
    expect(within(status).getByText("Нет данных")).toBeInTheDocument();
  });
});

describe("PipelineDashboard", () => {
  const overview = {
    total_jobs: 25, by_status: { queued: 0, running: 1, success: 20, failed: 4 }, unknown_status_jobs: 0, success_rate: 20 / 24,
    avg_duration_seconds: 12.5, max_duration_seconds: 30, duration_sample_size: 20, stage_status_counts: {},
    last_execution: { job_id: "job-1", dataset_name: "Река Ока", status: "success", finished_at: "2026-11-17T09:00:00+00:00" },
    orchestration: { mode: "local", jobs_with_orchestrator_run: 0, dag_status_polling: false },
  };
  const row = (i) => ({ job_id: `job-${i}`, dataset_id: "ds-1", dataset_name: "Река Ока", batch_id: `batch-${i}`, status: "success",
    started_at: null, finished_at: null, duration_seconds: 3, error_message: null, created_at: "2026-11-17T08:00:00+00:00" });

  beforeEach(() => {
    A.pipelineOverview.mockImplementation(() => ok(overview));
    A.pipelinePerformance.mockImplementation(() => ok({ series: [], stage_durations: [], status_distribution: {} }));
    A.pipelineErrors.mockImplementation(() => ok({ items: [], total: 0, by_type: {} }));
    A.pipelineJobs.mockImplementation(() => ok({ items: [row(1), row(2)], total: 25 }));
    A.pipelineJob.mockImplementation((id) => ok({
      job_id: id, dataset_name: "Река Ока", batch_id: "batch-1", status: "success", duration_seconds: 3, orchestrator_run_id: null, error_message: null,
      metrics: {}, assets: [], stage_timestamps_available: false,
      lifecycle: [{ stage: "bronze", label: "Bronze", status: "success", duration_seconds: 1, rows: 100 }, { stage: "ml", label: "ML", status: "not_run", duration_seconds: null, rows: null }],
    }));
  });

  it("computes headline KPIs from backend values and states what is not tracked", async () => {
    mount(<PipelineDashboard />);
    expect(await screen.findByText("Pipeline Success Rate")).toBeInTheDocument();
    expect(screen.getByText("83,3%")).toBeInTheDocument();
    expect(await screen.findByText("Не запускался")).toBeInTheDocument();
    expect(screen.getByText(/не опрашиваются/)).toBeInTheDocument();
    expect(screen.getByText(/Время начала и окончания отдельных этапов система не хранит/)).toBeInTheDocument();
  });

  it("status filter, search, sort and paging go to the server", async () => {
    mount(<PipelineDashboard />);
    await screen.findByText("Job Monitoring");
    await waitFor(() => expect(A.pipelineJobs).toHaveBeenCalled());
    expect(lastParams(A.pipelineJobs)).toMatchObject({ limit: 10, offset: 0, sort_by: "created_at", sort_dir: "desc" });

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Статус" }), "failed");
    await waitFor(() => expect(lastParams(A.pipelineJobs)).toMatchObject({ status: "failed", offset: 0 }));

    await userEvent.type(screen.getByRole("searchbox"), "abc");
    await waitFor(() => expect(lastParams(A.pipelineJobs)).toMatchObject({ search: "abc" }), { timeout: 2000 });

    await userEvent.click(screen.getByRole("button", { name: "Status" }));
    await waitFor(() => expect(lastParams(A.pipelineJobs)).toMatchObject({ sort_by: "status", sort_dir: "asc" }));

    await userEvent.click(screen.getByRole("button", { name: "Следующая страница" }));
    await waitFor(() => expect(lastParams(A.pipelineJobs)).toMatchObject({ offset: 10 }));
  });

  it("clicking a job loads its lifecycle", async () => {
    mount(<PipelineDashboard />);
    await userEvent.click(await screen.findByText("job-2".slice(0, 8)));
    await waitFor(() => expect(A.pipelineJob).toHaveBeenCalledWith("job-2", expect.anything()));
  });

  it("shows an honest empty state when there are no jobs", async () => {
    A.pipelineOverview.mockImplementation(() => ok({ ...overview, total_jobs: 0, success_rate: null, avg_duration_seconds: null, last_execution: null, by_status: { queued: 0, running: 0, success: 0, failed: 0 } }));
    A.pipelineJobs.mockImplementation(() => ok({ items: [], total: 0 }));
    mount(<PipelineDashboard />);
    expect(await screen.findByText("Задач обработки пока нет")).toBeInTheDocument();
    expect(screen.getAllByText("N/A").length).toBeGreaterThanOrEqual(3);
  });
});

describe("WaterQualityDashboard", () => {
  const dist = (extra = {}) => ({
    dataset_id: "ds-1", batch_id: "b1", parameter: "ph", rows_in_scope: 10, n: 10, null_count: 0,
    summary: { mean: 7, std: 0.1, min: 6, max: 8 }, percentiles: { median: 7, p05: 6.2 },
    histogram: { edges: [6, 7, 8], counts: [5, 5] }, boxplot: { low: 6, q1: 6.5, median: 7, q3: 7.5, high: 8, outliers: [], outlier_count: 0 },
    threshold: { rule: "ph_physical_range", min: 0, max: 14, below: 0, above: 2, description: "Допустимый диапазон из quality gate", kind: "quality_gate_validity_range" },
    ...extra,
  });

  beforeEach(() => {
    A.thresholds.mockImplementation(() => ok({ items: [{ parameter: "ph", min: 0, max: 14 }], regulatory_norms_configured: false }));
    A.stationMetrics.mockImplementation(() => ok([{ station_id: "s0", avg_value: 7, median_value: 7, min_value: 6, max_value: 8, std_value: 0.1, measurement_count: 5 }]));
    A.distribution.mockImplementation(() => ok(dist()));
    A.correlation.mockImplementation(() => ok({ parameters: ["ph", "temperature"], matrix: [[1, 0.2], [0.2, 1]], pair_counts: [[5, 5], [5, 5]], truncated: false, note: "Корреляция не доказывает причинно-следственную зависимость" }));
    A.measurements.mockImplementation(() => ok({ items: [{ row_number: 1, measured_at: "2026-01-01T00:00:00+00:00", station_id: "s0", value: 7.1, outside_validity_range: false }], total: 1 }, { total: 1 }));
  });

  it("parameter and station selectors change the backend queries", async () => {
    mount(<WaterQualityDashboard />);
    await waitFor(() => expect(A.distribution).toHaveBeenCalled());
    expect(lastParams(A.distribution)).toMatchObject({ dataset_id: "ds-1", parameter: "ph", station_id: "" });

    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Параметр" }), "temperature");
    await waitFor(() => expect(lastParams(A.distribution)).toMatchObject({ parameter: "temperature" }));
    expect(lastParams(A.measurements)).toMatchObject({ parameter: "temperature" });
    expect(A.trends).toHaveBeenLastCalledWith("ds-1", expect.objectContaining({ parameter: "temperature" }), expect.anything());

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Станция" }), "s1");
    await waitFor(() => expect(lastParams(A.distribution)).toMatchObject({ station_id: "s1" }));
    expect(lastParams(A.correlation)).toMatchObject({ station_id: "s1" });
    expect(lastParams(A.measurements)).toMatchObject({ station_id: "s1" });
  });

  it("labels thresholds as quality-gate ranges, not regulatory norms", async () => {
    mount(<WaterQualityDashboard />);
    const note = await screen.findByTestId("threshold-note");
    expect(note).toHaveTextContent("quality gate «ph_physical_range»");
    expect(note).toHaveTextContent("выше: 2");
    expect(screen.getByText(/причинно-следственную/)).toBeInTheDocument();
  });

  it("explains missing thresholds instead of inventing reference ranges", async () => {
    A.distribution.mockImplementation(() => ok(dist({ threshold: null })));
    mount(<WaterQualityDashboard />);
    expect(await screen.findByText(/нормативы качества воды не настроены/)).toBeInTheDocument();
  });

  it("shows an empty state when the selection has no values", async () => {
    A.distribution.mockImplementation(() => ok(dist({ n: 0, summary: null, percentiles: null, histogram: null, boxplot: null, threshold: null })));
    mount(<WaterQualityDashboard />);
    expect(await screen.findAllByText("Нет значений параметра в выбранной области")).not.toHaveLength(0);
  });

  it("tells the user when no dataset has analytics marts", async () => {
    A.martsDatasets.mockImplementation(() => ok([]));
    mount(<WaterQualityDashboard />);
    expect(await screen.findByText(/Нет наборов данных с построенными витринами/)).toBeInTheDocument();
    expect(A.waterCatalog).not.toHaveBeenCalled();
  });
});

describe("DataQualityDashboard", () => {
  const entry = (extra = {}) => ({
    dataset_id: "ds-1", dataset_name: "Река Ока", batch_id: "batch-aaa1", published_at: "2026-11-01T10:00:00+00:00", publish_status: "published",
    quality_status: "warning", quality_score: 0.75, rule_coverage: 1, critical_failures: 0, bronze_rows: 100, silver_rows: 98, gold_rows: 95,
    quarantined_rows: 3, removed_duplicates: 2, duplicate_rate: 0.02, null_cells: 4, checks_total: 4, checks_passed: 3, checks_failed: 1, checks_skipped: 0, ...extra,
  });
  const rule = (extra = {}) => ({ rule: "ph_range", rule_type: "between", category: "row", column: "ph", severity: "warning", status: "failed",
    failed_rows: 3, checked_rows: 98, failure_rate: 3 / 98, observed_value: 3, expected: "0..14", dataset_id: "ds-1", dataset_name: "Река Ока",
    batch_id: "batch-aaa1", job_id: "job-9", created_at: "2026-11-01T10:00:00+00:00", ...extra });

  beforeEach(() => {
    A.qualityOverview.mockImplementation(() => ok({
      scope: "latest_batch_per_dataset",
      kpis: { datasets_with_reports: 1, batches_total: 1, avg_quality_score: 0.75, avg_rule_coverage: 1, gold_rows: 95, silver_rows: 98, null_cells: 4,
        duplicates_removed: 2, quarantined_rows: 3, rules_passed: 3, rules_failed: 1, rules_skipped: 0 },
      status_distribution: { warning: 1 }, status_distribution_all_batches: { warning: 1 }, trend: [entry()], ranking: [entry()],
      layers: [{ dataset_id: "ds-1", dataset_name: "Река Ока", batch_id: "batch-aaa1", bronze_rows: 100, silver_rows: 98, gold_rows: 95, removed_duplicates: 2, quarantined_rows: 3, null_cells: 4 }],
    }));
    A.qualityColumns.mockImplementation(() => ok({ dataset_id: "ds-1", row_count: 95, columns: [{ name: "ph", data_type: "double", null_count: 5, null_percent: 5, unique_count: 80, is_system: false }],
      problem_columns: [{ name: "ph", data_type: "double", null_count: 5, null_percent: 5, unique_count: 80, is_system: false }], null_history: [] }));
    A.qualityRules.mockImplementation(() => ok({ items: [rule(), rule({ rule: "rows", rule_type: "min_rows", category: "dataset", checked_rows: null, failure_rate: null, status: "passed", failed_rows: 0 })], total: 2, summary: { by_status: { failed: 1, passed: 1 } } }, { total: 2 }));
  });

  it("shows KPIs and statuses exactly as the backend reports them", async () => {
    mount(<DataQualityDashboard />);
    expect(await screen.findByText("Overall Quality Score")).toBeInTheDocument();
    const kpiCard = screen.getByText("Overall Quality Score").closest("article");
    expect(within(kpiCard).getByText("0,75")).toBeInTheDocument();
    expect((await screen.findAllByText("WARNING")).length).toBeGreaterThan(0);
    expect(screen.getByText(/не разность/)).toBeInTheDocument();
  });

  it("failure rate exists only for row rules; dataset-level rules show N/A", async () => {
    mount(<DataQualityDashboard />);
    const table = (await screen.findByText("ph_range")).closest("table");
    const cells = within(table).getAllByRole("row").map((r) => r.textContent);
    expect(cells.find((c) => c.includes("ph_range"))).toContain("3,06%");
    expect(cells.find((c) => c.startsWith("rows"))).toContain("N/A");
  });

  it("rule filters and sorting are sent to the backend", async () => {
    mount(<DataQualityDashboard />);
    await screen.findByText("ph_range");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Статус" }), "failed");
    await waitFor(() => expect(lastParams(A.qualityRules)).toMatchObject({ status: "failed" }));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Severity" }), "critical");
    await waitFor(() => expect(lastParams(A.qualityRules)).toMatchObject({ severity: "critical", status: "failed" }));
    await userEvent.click(screen.getByRole("button", { name: "Failed" }));
    await waitFor(() => expect(lastParams(A.qualityRules)).toMatchObject({ sort_by: "failed_rows" }));
  });

  it("drill-down: ranking row selects the dataset and batch, rule row opens details", async () => {
    const navigate = mount(<DataQualityDashboard />);
    const ranking = (await screen.findByText("Dataset Quality Ranking")).closest("section");
    await userEvent.click(within(ranking).getByText("Река Ока"));
    await waitFor(() => expect(lastParams(A.qualityRules)).toMatchObject({ dataset_id: "ds-1", batch_id: "batch-aaa1" }));
    await userEvent.click(await screen.findByText("ph_range"));
    const panel = await screen.findByLabelText("Детали правила");
    expect(panel).toHaveTextContent("0..14");
    await userEvent.click(within(panel).getByRole("button", { name: "Открыть ETL job" }));
    expect(navigate).toHaveBeenCalledWith("etl", { jobId: "job-9" });
  });

  it("empty state when no quality reports exist", async () => {
    A.qualityOverview.mockImplementation(() => ok({
      scope: "latest_batch_per_dataset", kpis: { datasets_with_reports: 0, batches_total: 0, avg_quality_score: null, avg_rule_coverage: null, gold_rows: null,
        silver_rows: null, null_cells: null, duplicates_removed: null, quarantined_rows: null, rules_passed: null, rules_failed: null, rules_skipped: null },
      status_distribution: {}, status_distribution_all_batches: {}, trend: [], ranking: [], layers: [],
    }));
    A.qualityRules.mockImplementation(() => ok({ items: [], total: 0, summary: { by_status: {} } }));
    mount(<DataQualityDashboard />);
    expect((await screen.findAllByText("Отчётов качества пока нет")).length).toBeGreaterThan(0);
    expect(screen.getByText("Результатов проверок пока нет")).toBeInTheDocument();
  });
});

describe("MLAnalyticsDashboard", () => {
  const overview = (extra = {}) => ({ rows_scored: 240, anomalies: 12, normal: 228, anomaly_rate: 0.05, models_used: [{ model_name: "m", model_version: "v1" }],
    last_detection_at: "2026-11-01T10:00:00+00:00", last_run: { run_id: "run12345abc", status: "completed" }, registry: { models: 1, versions: 1, production: [] }, score_note: "n", ...extra });

  beforeEach(() => {
    A.mlOverview.mockImplementation(() => ok(overview()));
    A.models.mockImplementation(() => ok([{ model_name: "m", latest_version: "v1", production_version: null, versions: [{ model_version: "v1", status: "candidate" }] }]));
    A.mlRuns.mockImplementation(() => ok({ items: [], total: 0 }));
    A.drift.mockImplementation(() => ok({ available: false, thresholds: { warning: 0.1, alert: 0.25 }, reports: [], latest: null }));
    A.anomaliesSummary.mockImplementation(() => ok({ model: { model_name: "m", model_version: "v1" }, rows_scored: 240, anomalies: 12, by_station: [{ key: "s0", anomalies: 12, total: 80, rate: 0.15 }],
      by_batch: [{ key: "b1", anomalies: 12, total: 240, rate: 0.05 }], score_histogram: { edges: [0, 1], normal: [1], anomaly: [1] }, by_feature: [{ feature: "ph_dev", parameter: "ph", anomalies: 12 }], score_note: "шкала score" }));
    A.anomalySeries.mockImplementation(() => ok({ x_kind: "time", normal: [{ x: "2026-01-01T00:00:00+00:00", value: 7 }], anomalies: [{ x: "2026-01-02T00:00:00+00:00", value: 9 }], total_points: 2, downsampled: false }));
    A.anomalyScatter.mockImplementation(() => ok({ normal: [{ x: 1, y: 2 }], anomalies: [{ x: 5, y: 6 }], total_points: 2, downsampled: false }));
    A.anomalyRecords.mockImplementation(() => ok({ items: [], total: 0, parameters: ["ph"], model: {} }, { total: 0 }));
    A.modelDetail.mockImplementation(() => ok({ model_name: "m", active_version: null, detection_history: [], versions: [{ model_version: "v1", status: "candidate", algorithm: "IsolationForest",
      params: { contamination: 0.05 }, features: ["ph"], feature_version: "1.0", created_at: "2026-11-01T10:00:00+00:00", training: { batch_id: "b1", rows_train: 100, rows_total: 240 },
      evaluation: { train_anomaly_rate: 0.05, split: "temporal" }, has_ground_truth: false, ground_truth_metrics: null }] }));
  });

  it("shows N/A and an explanation when no detection has run", async () => {
    A.mlOverview.mockImplementation(() => ok(overview({ rows_scored: 0, anomalies: 0, normal: 0, anomaly_rate: null, models_used: [], last_detection_at: null, last_run: null })));
    mount(<MLAnalyticsDashboard />);
    expect(await screen.findByText("Нет результатов детекции")).toBeInTheDocument();
    expect(screen.getAllByText("N/A").length).toBeGreaterThanOrEqual(4);
    expect(screen.getByText("Запусков inference не зафиксировано")).toBeInTheDocument();
  });

  it("loads anomaly charts for the latest batch and refetches when the parameter changes", async () => {
    mount(<MLAnalyticsDashboard />);
    await waitFor(() => expect(A.anomalySeries).toHaveBeenCalled());
    expect(lastParams(A.anomalySeries)).toMatchObject({ dataset_id: "ds-1", batch_id: "b1", parameter: "ph", model_version: "v1" });
    await userEvent.selectOptions((await screen.findAllByRole("combobox", { name: "Параметр" }))[0], "temperature");
    await waitFor(() => expect(lastParams(A.anomalySeries)).toMatchObject({ parameter: "temperature" }));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Станция" }), "s0");
    await waitFor(() => expect(lastParams(A.anomalySeries)).toMatchObject({ station_id: "s0" }));
    expect(lastParams(A.anomalyRecords)).toMatchObject({ station_id: "s0" });
  });

  it("does not present metrics for a model without ground truth", async () => {
    mount(<MLAnalyticsDashboard />);
    await userEvent.click(await screen.findByText("candidate"));
    expect(await screen.findByText(/не показываются: модель обучена без размеченной ground truth/)).toBeInTheDocument();
    expect(screen.queryByText("precision")).not.toBeInTheDocument();
    expect(A.modelDetail).toHaveBeenCalledWith("m", expect.anything());
  });

  it("says drift monitoring is unavailable instead of drawing a chart", async () => {
    mount(<MLAnalyticsDashboard />);
    expect(await screen.findByText(/Отчёты о дрейфе не формировались/)).toBeInTheDocument();
  });
});
