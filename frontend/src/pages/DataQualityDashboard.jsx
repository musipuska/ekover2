import { useEffect, useMemo, useState } from "react";

import ChartCard from "../components/analytics/ChartCard";
import DashboardHeader from "../components/analytics/DashboardHeader";
import { CommonFilters, Field, SelectField } from "../components/analytics/DashboardFilters";
import DataTable from "../components/analytics/DataTable";
import KpiCard from "../components/analytics/KpiCard";
import StatusBadge from "../components/analytics/StatusBadge";
import EChart from "../components/charts/EChart";
import { barOption, donutOption, gaugeOption, lineOption } from "../components/charts/options";
import { useAsync } from "../hooks/useAsync";
import { useDashboard } from "../hooks/useDashboard";
import { analytics } from "../services/analyticsApi";
import { formatDate, formatInt, formatNumber, formatPercent, shortId } from "../utils/format";

const PAGE = 10;
const RULE_STATUS = ["passed", "failed", "skipped"].map((v) => ({ value: v, label: v }));
const SEVERITY = ["critical", "warning", "info"].map((v) => ({ value: v, label: v }));

export default function DataQualityDashboard() {
  const d = useDashboard();
  const base = { dataset_id: d.datasetId, ...d.period };
  const overview = useAsync((s) => analytics.qualityOverview(base, s), [d.datasetId, d.dateFrom, d.dateTo]);
  const ov = overview.data;
  const kpi = ov?.kpis;

  // Drill-down: набор → batch → отчёт → правила
  const scopeDataset = d.datasetId || ov?.layers[0]?.dataset_id || "";
  const [batch, setBatch] = useState("");
  const batches = useMemo(() => (ov?.trend ?? []).filter((t) => t.dataset_id === scopeDataset), [ov, scopeDataset]);
  const activeBatch = batches.some((b) => b.batch_id === batch) ? batch : "";
  const report = batches.find((b) => b.batch_id === activeBatch) ?? null;

  const columns = useAsync((s) => analytics.qualityColumns({ dataset_id: scopeDataset, batch_id: activeBatch }, s),
    [scopeDataset, activeBatch], Boolean(scopeDataset));

  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState({ by: "created_at", dir: "desc" });
  const [offset, setOffset] = useState(0);
  const [picked, setPicked] = useState(null);

  useEffect(() => {
    const timer = setTimeout(() => { setQuery(search.trim()); setOffset(0); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const rules = useAsync(
    (s) => analytics.qualityRules({ ...base, batch_id: activeBatch, status, severity, search: query,
      sort_by: sort.by, sort_dir: sort.dir, limit: PAGE, offset }, s),
    [d.datasetId, d.dateFrom, d.dateTo, activeBatch, status, severity, query, sort.by, sort.dir, offset],
  );

  const gauge = useMemo(() => kpi?.avg_quality_score != null && gaugeOption({ value: kpi.avg_quality_score, name: "Quality Score" }), [kpi]);

  const trendOption = useMemo(() => {
    const entries = ov?.trend ?? [];
    const keys = [...new Set(entries.map((t) => t.published_at))].sort();
    const ids = [...new Set(entries.map((t) => t.dataset_id))];
    return lineOption({
      categories: keys.map((k) => formatDate(k)),
      series: ids.map((id) => ({
        name: entries.find((t) => t.dataset_id === id).dataset_name,
        data: keys.map((key) => entries.find((t) => t.dataset_id === id && t.published_at === key)?.quality_score ?? null),
      })),
      yName: "Quality Score", zoom: false,
    });
  }, [ov]);

  const donut = useMemo(() => donutOption({ data: Object.entries(ov?.status_distribution ?? {}).map(([name, value]) => ({ name, value })) }), [ov]);

  const layers = useMemo(() => {
    const items = ov?.layers ?? [];
    return barOption({
      categories: items.map((i) => i.dataset_name),
      series: [
        { name: "Bronze", data: items.map((i) => i.bronze_rows) },
        { name: "Silver", data: items.map((i) => i.silver_rows) },
        { name: "Gold", data: items.map((i) => i.gold_rows) },
        { name: "Quarantine", data: items.map((i) => i.quarantined_rows), color: "#fbbf24" },
      ],
      yName: "строк",
    });
  }, [ov]);

  const dupes = useMemo(() => barOption({
    categories: (ov?.layers ?? []).map((i) => i.dataset_name),
    series: [{ name: "Удалено дубликатов", data: (ov?.layers ?? []).map((i) => i.removed_duplicates), color: "#a78bfa" }],
    yName: "строк", legend: false,
  }), [ov]);

  const nullBars = useMemo(() => {
    const items = (columns.data?.columns ?? []).filter((c) => !c.is_system);
    return barOption({
      categories: items.map((c) => c.name),
      series: [{ name: "Пропуски, %", data: items.map((c) => c.null_percent), color: "#fbbf24" }],
      yName: "%", horizontal: true, legend: false,
    });
  }, [columns.data]);

  const nullHistory = useMemo(() => {
    const history = columns.data?.null_history ?? [];
    const names = [...new Set(history.flatMap((h) => Object.keys(h.null_percent)))];
    return lineOption({
      categories: history.map((h) => formatDate(h.published_at)),
      series: names.map((name) => ({ name, data: history.map((h) => h.null_percent[name] ?? null) })),
      yName: "% пропусков", zoom: false,
    });
  }, [columns.data]);

  const refresh = () => { overview.reload(); columns.reload(); rules.reload(); };
  const noReports = ov && ov.layers.length === 0;

  return (
    <div className="dash">
      <DashboardHeader title="Data Quality" subtitle="Результаты Data Quality Gate и качество данных по слоям Bronze → Silver → Gold"
        updatedAt={overview.updatedAt} onRefresh={refresh} loading={overview.loading || rules.loading}>
        <CommonFilters />
      </DashboardHeader>

      {overview.error ? <ChartCard title="Quality KPIs" state={overview} /> : (
        <div className="kpi-grid">
          {overview.loading ? Array.from({ length: 9 }, (_, i) => <div key={i} className="kpi-card skeleton-card" aria-hidden="true" />) : (
            <>
              <KpiCard label="Overall Quality Score" display={formatNumber(kpi.avg_quality_score, 3)} description="Среднее по последнему batch каждого набора" />
              <KpiCard label="Total Rows (Gold)" value={kpi.gold_rows} description="Строки в Gold" />
              <KpiCard label="Null Cells" value={kpi.null_cells} description="Пропуски в Silver после очистки" />
              <KpiCard label="Duplicate Records" value={kpi.duplicates_removed} description="Удалено при дедупликации Bronze → Silver" />
              <KpiCard label="Quarantined Records" value={kpi.quarantined_rows} description="Исключены из Gold по правилам с quarantine" />
              <KpiCard label="Passed Rules" value={kpi.rules_passed} description="Выполненные и пройденные проверки" />
              <KpiCard label="Failed Rules" value={kpi.rules_failed} description="Проваленные проверки" />
              <KpiCard label="Rule Coverage" display={formatPercent(kpi.avg_rule_coverage)} description="Доля реально выполненных правил" />
              <KpiCard label="Batches" value={kpi.batches_total} description={`Наборов с отчётами: ${kpi.datasets_with_reports}`} />
            </>
          )}
        </div>
      )}

      <div className="dash-grid">
        <ChartCard title="Quality Score" state={overview} isEmpty={noReports || kpi?.avg_quality_score == null}
          emptyHint="Отчётов качества пока нет">
          {gauge && <EChart option={gauge} height={230} label="Индикатор Quality Score" />}
        </ChartCard>
        <ChartCard title="Quality Status Distribution" description="Последний batch каждого набора" state={overview}
          isEmpty={noReports || !Object.keys(ov?.status_distribution ?? {}).length}>
          <EChart option={donut} height={230} label="Статусы качества" />
        </ChartCard>
        <ChartCard title="Quality Trend" description="Score по времени публикации batch" state={overview} isEmpty={noReports} className="span-2">
          <EChart option={trendOption} height={260} label="Тренд Quality Score" />
        </ChartCard>
      </div>

      <ChartCard title="Dataset Quality Ranking" description="Нажмите на строку, чтобы перейти к набору данных" state={overview} isEmpty={noReports}
        className="span-2">
        <DataTable rowKey={(r) => `${r.dataset_id}:${r.batch_id}`} rows={ov?.ranking ?? []} selectedKey={report && `${report.dataset_id}:${report.batch_id}`}
          onRowClick={(r) => { d.setDatasetId(r.dataset_id); setBatch(r.batch_id); setOffset(0); }}
          columns={[
            { key: "dataset_name", header: "Набор", sortable: true },
            { key: "quality_status", header: "Статус", render: (r) => <StatusBadge value={r.quality_status} /> },
            { key: "quality_score", header: "Score", align: "right", sortable: true, render: (r) => formatNumber(r.quality_score, 3) },
            { key: "rule_coverage", header: "Coverage", align: "right", render: (r) => formatPercent(r.rule_coverage) },
            { key: "checks_failed", header: "Провалено", align: "right", render: (r) => formatInt(r.checks_failed) },
            { key: "published_at", header: "Опубликован", render: (r) => formatDate(r.published_at) },
          ]} />
      </ChartCard>

      <div className="dash-grid">
        <ChartCard title="Bronze / Silver / Gold" state={overview} isEmpty={noReports}
          description="Каждое значение — отдельное измерение этапа, а не разность: Bronze→Silver уменьшает дедупликация, Silver→Gold — quarantine">
          <EChart option={layers} height={280} label="Строки по слоям" />
        </ChartCard>
        <ChartCard title="Duplicate Analysis" state={overview} isEmpty={noReports || (ov?.layers ?? []).every((l) => l.removed_duplicates == null)}>
          <EChart option={dupes} height={200} label="Дубликаты по наборам" />
          <DataTable rowKey={(r) => r.dataset_id} rows={ov?.trend ? [...ov.ranking] : []} columns={[
            { key: "dataset_name", header: "Набор" },
            { key: "removed_duplicates", header: "Удалено", align: "right", render: (r) => formatInt(r.removed_duplicates) },
            { key: "duplicate_rate", header: "Доля от Bronze", align: "right", render: (r) => formatPercent(r.duplicate_rate, 2) },
          ]} />
        </ChartCard>
      </div>

      <ChartCard title="Batch и Quality Report" description={scopeDataset ? `Набор: ${d.datasetName(scopeDataset)}` : undefined}
        state={overview} isEmpty={noReports || !batches.length} emptyHint="У выбранного набора нет опубликованных batch" className="span-2">
        <DataTable rowKey={(r) => r.batch_id} rows={batches} selectedKey={activeBatch} onRowClick={(r) => { setBatch(r.batch_id); setOffset(0); }}
          columns={[
            { key: "batch_id", header: "Batch", render: (r) => <code title={r.batch_id}>{shortId(r.batch_id)}</code> },
            { key: "quality_status", header: "Статус", render: (r) => <StatusBadge value={r.quality_status} /> },
            { key: "quality_score", header: "Score", align: "right", sortable: true, render: (r) => formatNumber(r.quality_score, 3) },
            { key: "bronze_rows", header: "Bronze", align: "right", render: (r) => formatInt(r.bronze_rows) },
            { key: "silver_rows", header: "Silver", align: "right", render: (r) => formatInt(r.silver_rows) },
            { key: "gold_rows", header: "Gold", align: "right", render: (r) => formatInt(r.gold_rows) },
            { key: "published_at", header: "Опубликован", render: (r) => formatDate(r.published_at) },
          ]} />
        {report && (
          <dl className="summary-grid" aria-label="Quality report">
            <div><dt>Критических провалов</dt><dd>{formatInt(report.critical_failures)}</dd></div>
            <div><dt>Проверок выполнено</dt><dd>{formatInt(report.checks_total)}</dd></div>
            <div><dt>Пройдено / провалено</dt><dd>{formatInt(report.checks_passed)} / {formatInt(report.checks_failed)}</dd></div>
            <div><dt>Пропущено</dt><dd>{formatInt(report.checks_skipped)}</dd></div>
            <div><dt>Quarantine</dt><dd>{formatInt(report.quarantined_rows)}</dd></div>
            <div><dt>Null cells</dt><dd>{formatInt(report.null_cells)}</dd></div>
          </dl>
        )}
      </ChartCard>

      <div className="dash-grid">
        <ChartCard title="Missing Values" description={scopeDataset ? `Пропуски по колонкам · ${d.datasetName(scopeDataset)}` : undefined}
          state={scopeDataset ? columns : { loading: false, error: null }}
          isEmpty={!scopeDataset || !(columns.data?.columns ?? []).some((c) => !c.is_system)} emptyHint="Профиль набора данных не сформирован">
          <EChart option={nullBars} height={Math.max(220, (columns.data?.columns.length ?? 0) * 30 + 60)} label="Пропуски по колонкам" />
        </ChartCard>
        <ChartCard title="Динамика пропусков между batch" state={scopeDataset ? columns : { loading: false, error: null }}
          isEmpty={!scopeDataset || (columns.data?.null_history.length ?? 0) < 1} emptyHint="История профилей отсутствует">
          <EChart option={nullHistory} height={260} label="Динамика пропусков" />
        </ChartCard>
      </div>
      <ChartCard title="Проблемные колонки" state={scopeDataset ? columns : { loading: false, error: null }}
        isEmpty={!scopeDataset || !columns.data?.problem_columns.length} emptyHint="Колонок с пропусками нет" className="span-2">
        <DataTable rowKey={(r) => r.name} rows={columns.data?.problem_columns ?? []} columns={[
          { key: "name", header: "Колонка", sortable: true },
          { key: "data_type", header: "Тип" },
          { key: "null_count", header: "Пропусков", align: "right", sortable: true, render: (r) => formatInt(r.null_count) },
          { key: "null_percent", header: "Пропусков, %", align: "right", sortable: true, render: (r) => formatNumber(r.null_percent, 2) },
          { key: "unique_count", header: "Уникальных", align: "right", render: (r) => formatInt(r.unique_count) },
        ]} />
      </ChartCard>

      <ChartCard title="Quality Rules Monitoring" state={rules} className="span-2"
        isEmpty={rules.data && rules.data.total === 0 && !query && !status && !severity}
        emptyHint="Результатов проверок пока нет"
        description={activeBatch ? `Batch ${shortId(activeBatch)}` : "Все batch выбранной области"}
        actions={(
          <>
            <Field label="Поиск"><input type="search" placeholder="Правило или колонка" value={search} onChange={(e) => setSearch(e.target.value)} /></Field>
            <SelectField label="Статус" value={status} placeholder="Все" options={RULE_STATUS} onChange={(v) => { setStatus(v); setOffset(0); }} />
            <SelectField label="Severity" value={severity} placeholder="Все" options={SEVERITY} onChange={(v) => { setSeverity(v); setOffset(0); }} />
          </>
        )}>
        {rules.data && (rules.data.total === 0 ? <p className="dash-note">По заданным условиям правил не найдено.</p> : (
          <DataTable rowKey={(r) => `${r.batch_id}:${r.rule}`} rows={rules.data.items} selectedKey={picked && `${picked.batch_id}:${picked.rule}`}
            sort={sort} onSort={(next) => { setSort(next); setOffset(0); }} onRowClick={setPicked}
            page={{ limit: PAGE, offset, total: rules.data.total }} onPage={setOffset}
            columns={[
              { key: "rule", header: "Rule Name", sortable: true },
              { key: "category", header: "Category", render: (r) => `${r.category} · ${r.rule_type ?? "—"}` },
              { key: "severity", header: "Severity", sortable: true, render: (r) => <StatusBadge value={r.severity} /> },
              { key: "status", header: "Status", sortable: true, render: (r) => <StatusBadge value={r.status} /> },
              { key: "failed_rows", header: "Failed", align: "right", sortable: true, render: (r) => formatInt(r.failed_rows) },
              { key: "checked_rows", header: "Checked", align: "right", render: (r) => formatInt(r.checked_rows) },
              { key: "failure_rate", header: "Failure Rate", align: "right", render: (r) => formatPercent(r.failure_rate, 2) },
              { key: "created_at", header: "Timestamp", sortable: true, render: (r) => formatDate(r.created_at) },
            ]} />
        ))}
        {picked && (
          <div className="detail-panel" aria-label="Детали правила">
            <h4>{picked.rule}</h4>
            <p>
              Набор: {picked.dataset_name} · batch <code>{shortId(picked.batch_id)}</code> · колонка: {picked.column ?? "—"} ·
              ожидание: {picked.expected ?? "—"} · наблюдаемое значение: {formatNumber(picked.observed_value, 4)}
            </p>
            <p className="dash-note">«Checked» и «Failure Rate» рассчитываются только для построчных правил (по числу строк Silver); для правил уровня набора они не определены.</p>
            {picked.job_id && <button type="button" className="dash-button" onClick={() => d.navigate("etl", { jobId: picked.job_id })}>Открыть ETL job</button>}
          </div>
        )}
        {rules.data?.summary && Object.keys(rules.data.summary.by_status).length > 0 && (
          <p className="dash-note">Статусы в выборке: {Object.entries(rules.data.summary.by_status).map(([k, v]) => `${k}: ${v}`).join(", ")}</p>
        )}
      </ChartCard>
    </div>
  );
}
