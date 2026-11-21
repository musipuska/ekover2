import { useEffect, useMemo, useState } from "react";
import { ArrowRight } from "lucide-react";

import ChartCard from "../components/analytics/ChartCard";
import DashboardHeader from "../components/analytics/DashboardHeader";
import { CommonFilters, Field, SelectField } from "../components/analytics/DashboardFilters";
import DataTable from "../components/analytics/DataTable";
import KpiCard from "../components/analytics/KpiCard";
import StatusBadge from "../components/analytics/StatusBadge";
import EChart from "../components/charts/EChart";
import { barOption, donutOption, lineOption } from "../components/charts/options";
import { useAsync } from "../hooks/useAsync";
import { useDashboard } from "../hooks/useDashboard";
import { analytics } from "../services/analyticsApi";
import { formatDate, formatDuration, formatInt, formatPercent, shortId } from "../utils/format";

const PAGE_SIZE = 10;
const STATUS_OPTIONS = ["queued", "running", "success", "failed"].map((v) => ({ value: v, label: v }));

function Lifecycle({ jobId }) {
  const state = useAsync((s) => analytics.pipelineJob(jobId, s), [jobId], Boolean(jobId));
  const job = state.data;
  return (
    <ChartCard title="ETL Lifecycle" state={state} isEmpty={!jobId}
      description={job ? `Job ${shortId(job.job_id)} · ${job.dataset_name} · batch ${shortId(job.batch_id)}` : "Выберите задачу в таблице ниже"}
      emptyHint="Задач обработки пока нет" className="span-2">
      {job && (
        <>
          <ol className="lifecycle" aria-label="Этапы обработки">
            {job.lifecycle.map((stage, index) => (
              <li key={stage.stage} className={`stage stage-${stage.status}`}>
                <strong>{stage.label}</strong>
                <StatusBadge value={stage.status} />
                <span>{stage.duration_seconds != null ? formatDuration(stage.duration_seconds) : "—"}</span>
                <span>{stage.rows != null ? `${formatInt(stage.rows)} строк` : ""}</span>
                {index < job.lifecycle.length - 1 && <ArrowRight className="stage-arrow" size={16} />}
              </li>
            ))}
          </ol>
          <p className="dash-note">
            Время начала и окончания отдельных этапов система не хранит — только общее время задачи
            ({formatDuration(job.duration_seconds)}) и длительность этапов Spark.
            Статус DAG-run из Airflow не опрашивается{job.orchestrator_run_id ? `; run id: ${job.orchestrator_run_id}` : ""}.
          </p>
          {job.error_message && <div className="dash-error inline" role="alert"><span>{job.error_message}</span></div>}
        </>
      )}
    </ChartCard>
  );
}

export default function PipelineDashboard() {
  const d = useDashboard();
  const base = { dataset_id: d.datasetId, ...d.period };
  const deps = [d.datasetId, d.dateFrom, d.dateTo];

  const overview = useAsync((s) => analytics.pipelineOverview(base, s), deps);
  const performance = useAsync((s) => analytics.pipelinePerformance(base, s), deps);
  const errors = useAsync((s) => analytics.pipelineErrors({ ...base, limit: 10 }, s), deps);

  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState({ by: "created_at", dir: "desc" });
  const [offset, setOffset] = useState(0);
  const [picked, setPicked] = useState(d.navParams.jobId ?? "");

  useEffect(() => {
    const timer = setTimeout(() => { setQuery(search.trim()); setOffset(0); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const jobs = useAsync(
    (s) => analytics.pipelineJobs({ ...base, status, search: query, sort_by: sort.by, sort_dir: sort.dir, limit: PAGE_SIZE, offset }, s),
    [...deps, status, query, sort.by, sort.dir, offset],
  );
  const selectedJobId = picked || overview.data?.last_execution?.job_id || "";

  const ov = overview.data;
  const series = useMemo(() => performance.data?.series ?? [], [performance.data]);
  const days = useMemo(() => series.map((i) => i.date), [series]);

  const durationOption = useMemo(() => lineOption({
    categories: days, series: [{ name: "Средняя длительность, с", data: series.map((i) => i.avg_duration_seconds) }], yName: "секунды", zoom: false,
  }), [days, series]);
  const volumeOption = useMemo(() => barOption({
    categories: days,
    series: [{ name: "Silver", data: series.map((i) => i.rows_silver) }, { name: "Gold", data: series.map((i) => i.rows_gold) }],
    yName: "строк",
  }), [days, series]);
  const failedOption = useMemo(() => lineOption({
    categories: days, series: [{ name: "Ошибки", data: series.map((i) => i.failed), color: "#fb7185" }], yName: "задач", zoom: false, area: true,
  }), [days, series]);
  const statusOption = useMemo(() => donutOption({
    data: Object.entries(performance.data?.status_distribution ?? {}).map(([name, value]) => ({ name, value })),
  }), [performance.data]);
  const stageOption = useMemo(() => barOption({
    categories: (performance.data?.stage_durations ?? []).map((i) => i.stage),
    series: [{ name: "Среднее, с", data: (performance.data?.stage_durations ?? []).map((i) => i.avg_seconds) },
      { name: "Максимум, с", data: (performance.data?.stage_durations ?? []).map((i) => i.max_seconds) }],
    yName: "секунды",
  }), [performance.data]);

  const last = ov?.last_execution;
  const refresh = () => { overview.reload(); performance.reload(); errors.reload(); jobs.reload(); };
  const loading = overview.loading || performance.loading || jobs.loading;

  return (
    <div className="dash">
      <DashboardHeader title="ETL & Pipeline Monitoring" subtitle="Фактическое состояние обработки данных"
        updatedAt={overview.updatedAt} onRefresh={refresh} loading={loading}>
        <CommonFilters />
      </DashboardHeader>

      {overview.error ? <ChartCard title="Pipeline Overview" state={overview} /> : (
        <div className="kpi-grid">
          {overview.loading ? Array.from({ length: 7 }, (_, i) => <div key={i} className="kpi-card skeleton-card" aria-hidden="true" />) : (
            <>
              <KpiCard label="Всего задач" value={ov.total_jobs} description="Все ETL-задачи за период" />
              <KpiCard label="Успешно" value={ov.by_status.success} description="status = success" />
              <KpiCard label="Ошибки" value={ov.by_status.failed} description="status = failed" />
              <KpiCard label="Выполняются" value={ov.by_status.running} description="status = running (хранится в БД)" />
              <KpiCard label="Pipeline Success Rate" display={formatPercent(ov.success_rate)} description="Успешные / завершённые (queued и running не входят)" />
              <KpiCard label="Средняя длительность" display={formatDuration(ov.avg_duration_seconds)}
                description={`По ${ov.duration_sample_size} успешным задачам`} />
              <KpiCard label="Последний запуск" display={last ? formatDate(last.finished_at ?? last.started_at ?? last.created_at) : "N/A"}
                description={last ? `${last.dataset_name} · ${last.status}` : "Задач не было"} />
            </>
          )}
        </div>
      )}

      <div className="dash-grid">
        <Lifecycle jobId={selectedJobId} />
        <ChartCard title="Оркестрация" state={overview} height={80}>
          {ov && (
            <div className="orchestration">
              <p>Режим: <strong>{ov.orchestration.mode}</strong></p>
              <p>Задач с привязкой к DAG-run: <strong>{ov.orchestration.jobs_with_orchestrator_run}</strong></p>
              <p className="dash-note">
                Backend только запускает DAG в Airflow и хранит его run id; статусы task runs из Airflow не опрашиваются,
                запуск DAG из интерфейса не предусмотрен.
              </p>
            </div>
          )}
        </ChartCard>
      </div>

      <div className="dash-grid">
        <ChartCard title="ETL Duration Trend" description="Средняя длительность успешных задач по дням" state={performance}
          isEmpty={!series.some((i) => i.avg_duration_seconds != null)} emptyHint="Нет завершённых задач с временем выполнения">
          <EChart option={durationOption} height={240} label="Тренд длительности ETL" />
        </ChartCard>
        <ChartCard title="Job Status Distribution" state={performance}
          isEmpty={!Object.keys(performance.data?.status_distribution ?? {}).length}>
          <EChart option={statusOption} height={240} label="Распределение статусов задач" />
        </ChartCard>
        <ChartCard title="Processing Volume Trend" description="Строки в Silver и Gold по дням (из метрик задач)" state={performance}
          isEmpty={!series.some((i) => i.rows_silver || i.rows_gold)} emptyHint="Метрики объёма не записаны">
          <EChart option={volumeOption} height={240} label="Объём обработки" />
        </ChartCard>
        <ChartCard title="Failed Jobs Trend" state={performance} isEmpty={!series.length}>
          <EChart option={failedOption} height={240} label="Тренд ошибок" />
        </ChartCard>
        <ChartCard title="Длительность этапов" description="Секунды по данным метрик задач" state={performance}
          isEmpty={!performance.data?.stage_durations.length} emptyHint="Метрики этапов не записаны">
          <EChart option={stageOption} height={240} label="Длительность этапов" />
        </ChartCard>
        <ChartCard title="Error Monitoring" state={errors} isEmpty={!errors.data?.items.length} emptyHint="Ошибок обработки нет"
          description={errors.data ? `Всего ошибок: ${errors.data.total}` : undefined}>
          <DataTable rowKey={(r) => r.job_id} rows={errors.data?.items ?? []} onRowClick={(r) => setPicked(r.job_id)}
            columns={[
              { key: "error_type", header: "Тип" },
              { key: "dataset_name", header: "Набор" },
              { key: "stage", header: "Этап" },
              { key: "message", header: "Описание" },
              { key: "occurred_at", header: "Когда", render: (r) => formatDate(r.occurred_at) },
            ]} />
        </ChartCard>
      </div>

      <ChartCard title="Job Monitoring" state={jobs} isEmpty={jobs.data && jobs.data.total === 0 && !query && !status}
        emptyHint="Задач обработки пока нет"
        actions={(
          <>
            <Field label="Поиск">
              <input type="search" placeholder="Job, batch или набор" value={search} onChange={(e) => setSearch(e.target.value)} />
            </Field>
            <SelectField label="Статус" value={status} placeholder="Все"
              onChange={(v) => { setStatus(v); setOffset(0); }} options={STATUS_OPTIONS} />
          </>
        )} className="span-2">
        {jobs.data && (
          jobs.data.total === 0
            ? <p className="dash-note">По заданным условиям задач не найдено.</p>
            : (
              <DataTable rowKey={(r) => r.job_id} rows={jobs.data.items} selectedKey={selectedJobId}
                sort={sort} onSort={(next) => { setSort(next); setOffset(0); }}
                page={{ limit: PAGE_SIZE, offset, total: jobs.data.total }} onPage={setOffset}
                onRowClick={(r) => setPicked(r.job_id)}
                columns={[
                  { key: "job_id", header: "Job ID", render: (r) => <code title={r.job_id}>{shortId(r.job_id)}</code> },
                  { key: "dataset", header: "Dataset", sortable: true, render: (r) => r.dataset_name },
                  { key: "batch_id", header: "Batch ID", render: (r) => <code title={r.batch_id}>{shortId(r.batch_id)}</code> },
                  { key: "status", header: "Status", sortable: true, render: (r) => <StatusBadge value={r.status} /> },
                  { key: "started_at", header: "Started At", sortable: true, render: (r) => formatDate(r.started_at) },
                  { key: "finished_at", header: "Completed At", sortable: true, render: (r) => formatDate(r.finished_at) },
                  { key: "duration_seconds", header: "Duration", align: "right", render: (r) => formatDuration(r.duration_seconds) },
                  { key: "error_message", header: "Error", render: (r) => r.error_message ?? "—" },
                ]} />
            )
        )}
      </ChartCard>
    </div>
  );
}
