import { useMemo, useState } from "react";

import ChartCard from "../components/analytics/ChartCard";
import DashboardHeader from "../components/analytics/DashboardHeader";
import { CommonFilters, SelectField } from "../components/analytics/DashboardFilters";
import DataTable from "../components/analytics/DataTable";
import KpiCard from "../components/analytics/KpiCard";
import StatusBadge from "../components/analytics/StatusBadge";
import EChart from "../components/charts/EChart";
import { barOption, donutOption, lineOption } from "../components/charts/options";
import { useAsync } from "../hooks/useAsync";
import { useDashboard } from "../hooks/useDashboard";
import { analytics } from "../services/analyticsApi";
import { formatDate, formatNumber, shortId } from "../utils/format";
import { aggregateTrends } from "../utils/series";

function WaterOverview() {
  const d = useDashboard();
  const dataset = d.analyticsDatasetId;
  const [chosen, setChosen] = useState("");

  const catalog = useAsync((s) => analytics.waterCatalog({ dataset_id: dataset }, s), [dataset], Boolean(dataset));
  const parameters = catalog.data?.parameters ?? [];
  const parameter = parameters.includes(chosen) ? chosen : (parameters[0] ?? "");

  const trends = useAsync(
    (s) => analytics.trends(dataset, { parameter, limit: 10000, ...d.period }, s),
    [dataset, parameter, d.dateFrom, d.dateTo],
    Boolean(dataset && parameter),
  );

  const points = useMemo(() => aggregateTrends(trends.data ?? [], "day").__all__ ?? [], [trends.data]);
  const option = useMemo(() => lineOption({
    categories: points.map((p) => p.key),
    series: [
      { name: "Среднее", data: points.map((p) => p.avg) },
      { name: "Минимум", data: points.map((p) => p.min) },
      { name: "Максимум", data: points.map((p) => p.max) },
    ],
    yName: parameter,
  }), [points, parameter]);

  const state = !dataset ? { loading: false, error: null } : (catalog.error || catalog.loading ? catalog : trends);

  return (
    <ChartCard
      title="Water Quality Overview"
      description={dataset ? `Дневная динамика по всем станциям · ${d.datasetName(dataset)}` : "Динамика показателей"}
      state={state}
      isEmpty={!dataset || !parameter || points.length === 0}
      emptyHint={!dataset ? "Аналитические витрины ещё не построены" : "Нет измерений за выбранный период"}
      className="span-2"
      actions={parameters.length > 0 && (
        <SelectField label="Параметр" value={parameter} onChange={setChosen}
          options={parameters.map((p) => ({ value: p, label: p }))} />
      )}
    >
      <EChart option={option} height={300} label={`Динамика показателя ${parameter}`} />
    </ChartCard>
  );
}

export default function OverviewDashboard() {
  const d = useDashboard();
  const state = useAsync(
    (s) => analytics.summary({ dataset_id: d.datasetId, ...d.period }, s),
    [d.datasetId, d.dateFrom, d.dateTo],
  );
  const summary = state.data;

  const activity = useMemo(() => barOption({
    categories: (summary?.dataset_activity ?? []).map((i) => i.date),
    series: [{ name: "Загружено наборов", data: (summary?.dataset_activity ?? []).map((i) => i.datasets) }],
    yName: "шт.", legend: false,
  }), [summary]);

  const processing = useMemo(() => barOption({
    categories: (summary?.processing_activity ?? []).map((i) => i.date),
    series: [
      { name: "Успешно", data: (summary?.processing_activity ?? []).map((i) => i.success), color: "#34d399" },
      { name: "Ошибки", data: (summary?.processing_activity ?? []).map((i) => i.failed), color: "#fb7185" },
    ],
    yName: "задач", stack: true,
  }), [summary]);

  const quality = useMemo(() => donutOption({
    data: Object.entries(summary?.quality_distribution ?? {}).map(([name, value]) => ({ name, value })),
  }), [summary]);

  const anomalies = useMemo(() => barOption({
    categories: (summary?.anomaly_overview.by_station ?? []).map((i) => i.key),
    series: [{ name: "Аномалии", data: (summary?.anomaly_overview.by_station ?? []).map((i) => i.anomalies), color: "#fb7185" }],
    yName: "шт.", legend: false,
  }), [summary]);

  const recent = summary?.recent;
  const status = summary?.platform_status;

  return (
    <div className="dash">
      <DashboardHeader title="Executive Overview" subtitle="Состояние данных, обработки, качества и аналитики"
        updatedAt={state.updatedAt} onRefresh={state.reload} loading={state.loading}>
        <CommonFilters />
      </DashboardHeader>

      <ChartCard title="Статус платформы" state={state} height={60} className="status-card">
        {status && (
          <div className="platform-status">
            <StatusBadge value={status.status} />
            <ul>{status.reasons.length ? status.reasons.map((r) => <li key={r}>{r}</li>) : <li>Замечаний нет</li>}</ul>
          </div>
        )}
      </ChartCard>

      <div className="kpi-grid">
        {state.loading && !summary
          ? Array.from({ length: 8 }, (_, i) => <div key={i} className="kpi-card skeleton-card" aria-hidden="true" />)
          : (summary?.kpis ?? []).map((k) => (
            <KpiCard key={k.key} label={k.label} value={k.value} unit={k.unit} description={k.description} delta={k.delta} valueKey={k.key} />
          ))}
      </div>
      {state.error && <ChartCard title="KPI" state={state} />}

      <div className="dash-grid">
        <ChartCard title="Dataset Activity" description="Загрузка наборов данных по дням" state={state}
          isEmpty={!summary?.dataset_activity.length} emptyHint="За период нет загруженных наборов">
          <EChart option={activity} height={260} label="Загрузка датасетов по дням" />
        </ChartCard>
        <ChartCard title="Processing Activity" description="ETL-задачи по дате создания" state={state}
          isEmpty={!summary?.processing_activity.length} emptyHint="За период нет задач обработки">
          <EChart option={processing} height={260} label="Обработка по дням" />
        </ChartCard>
        <WaterOverview />
        <ChartCard title="Data Quality Distribution" description="Статус quality gate последнего batch каждого набора"
          state={state} isEmpty={!Object.keys(summary?.quality_distribution ?? {}).length} emptyHint="Отчётов качества пока нет">
          <EChart option={quality} height={260} label="Распределение статусов качества" />
        </ChartCard>
        <ChartCard title="Anomaly Overview" description={summary?.anomaly_overview.model
          ? `Аномалии по станциям · ${summary.anomaly_overview.model.model_name} ${summary.anomaly_overview.model.model_version}` : "Аномалии по станциям"}
          state={state} isEmpty={!summary?.anomaly_overview.by_station.length}
          emptyHint="Детекция ещё не запускалась или нет колонки станции">
          <EChart option={anomalies} height={260} label="Аномалии по станциям" />
        </ChartCard>
      </div>

      <div className="dash-grid">
        <ChartCard title="Последние наборы данных" state={state} isEmpty={!recent?.datasets.length}>
          <DataTable rowKey={(r) => r.id} rows={recent?.datasets ?? []}
            onRowClick={() => d.navigate("datasets")}
            columns={[
              { key: "name", header: "Название", sortable: true },
              { key: "status", header: "Статус", render: (r) => <StatusBadge value={r.status} /> },
              { key: "created_at", header: "Загружен", render: (r) => formatDate(r.created_at), sortable: true },
            ]} />
        </ChartCard>
        <ChartCard title="Последние ETL jobs" state={state} isEmpty={!recent?.jobs.length}>
          <DataTable rowKey={(r) => r.job_id} rows={recent?.jobs ?? []}
            onRowClick={(r) => d.navigate("etl", { jobId: r.job_id })}
            columns={[
              { key: "job_id", header: "Job", render: (r) => shortId(r.job_id) },
              { key: "dataset_name", header: "Набор" },
              { key: "status", header: "Статус", render: (r) => <StatusBadge value={r.status} /> },
              { key: "created_at", header: "Создан", render: (r) => formatDate(r.created_at) },
            ]} />
        </ChartCard>
        <ChartCard title="Последние Quality Reports" state={state} isEmpty={!recent?.quality_reports.length}>
          <DataTable rowKey={(r) => `${r.dataset_id}:${r.batch_id}`} rows={recent?.quality_reports ?? []}
            onRowClick={(r) => { d.setDatasetId(r.dataset_id); d.navigate("quality"); }}
            columns={[
              { key: "dataset_name", header: "Набор" },
              { key: "quality_status", header: "Статус", render: (r) => <StatusBadge value={r.quality_status} /> },
              { key: "quality_score", header: "Score", align: "right", render: (r) => formatNumber(r.quality_score, 3) },
              { key: "published_at", header: "Опубликован", render: (r) => formatDate(r.published_at) },
            ]} />
        </ChartCard>
        <ChartCard title="Последние ошибки" state={state} isEmpty={!recent?.errors.length} emptyHint="Ошибок обработки нет">
          <DataTable rowKey={(r) => r.job_id} rows={recent?.errors ?? []}
            onRowClick={(r) => d.navigate("etl", { jobId: r.job_id })}
            columns={[
              { key: "error_type", header: "Тип" },
              { key: "dataset_name", header: "Набор" },
              { key: "message", header: "Сообщение" },
              { key: "occurred_at", header: "Когда", render: (r) => formatDate(r.occurred_at) },
            ]} />
        </ChartCard>
      </div>
    </div>
  );
}
