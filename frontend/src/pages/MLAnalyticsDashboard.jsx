import { useMemo, useState } from "react";

import ChartCard from "../components/analytics/ChartCard";
import DashboardHeader from "../components/analytics/DashboardHeader";
import { CommonFilters, SelectField } from "../components/analytics/DashboardFilters";
import DataTable from "../components/analytics/DataTable";
import KpiCard from "../components/analytics/KpiCard";
import StatusBadge from "../components/analytics/StatusBadge";
import EChart from "../components/charts/EChart";
import { barOption, histogramOption, lineOption, scatterOption } from "../components/charts/options";
import { useAsync } from "../hooks/useAsync";
import { useDashboard } from "../hooks/useDashboard";
import { analytics } from "../services/analyticsApi";
import { formatDate, formatInt, formatNumber, formatPercent, shortId } from "../utils/format";

const PAGE = 10;

function ModelCard({ name, onClose }) {
  const state = useAsync((s) => analytics.modelDetail(name, s), [name], Boolean(name));
  const detail = state.data;
  return (
    <ChartCard title={`Модель ${name}`} state={state} className="span-2"
      description={detail ? `Активная (production) версия: ${detail.active_version ?? "не назначена"}` : undefined}
      actions={<button type="button" className="dash-button ghost" onClick={onClose}>Закрыть</button>}>
      {detail && (
        <>
          {detail.versions.map((v) => {
            const ev = v.evaluation ?? {};
            return (
              <article key={v.model_version} className="model-version">
                <h4>{v.model_version} <StatusBadge value={v.status} /></h4>
                <dl className="summary-grid">
                  <div><dt>Алгоритм</dt><dd>{v.algorithm ?? "—"}</dd></div>
                  <div><dt>Обучена</dt><dd>{formatDate(v.created_at)}</dd></div>
                  <div><dt>Batch обучения</dt><dd>{shortId(v.training.batch_id)}</dd></div>
                  <div><dt>Строк обучения</dt><dd>{formatInt(v.training.rows_train)} из {formatInt(v.training.rows_total)}</dd></div>
                  <div><dt>Contamination</dt><dd>{v.params?.contamination ?? "—"}</dd></div>
                  <div><dt>Версия признаков</dt><dd>{v.feature_version ?? "—"}</dd></div>
                </dl>
                <p><strong>Признаки ({v.features?.length ?? 0}):</strong> {(v.features ?? []).join(", ") || "—"}</p>
                <dl className="summary-grid">
                  <div><dt>Доля аномалий (train)</dt><dd>{formatPercent(ev.train_anomaly_rate, 2)}</dd></div>
                  <div><dt>Доля аномалий (test)</dt><dd>{formatPercent(ev.test_anomaly_rate, 2)}</dd></div>
                  <div><dt>Сдвиг доли</dt><dd>{formatNumber(ev.rate_shift, 4)}</dd></div>
                  <div><dt>Разбиение</dt><dd>{ev.split ?? "—"}</dd></div>
                </dl>
                {v.has_ground_truth ? (
                  <dl className="summary-grid" aria-label="Метрики на размеченных данных">
                    {["precision", "recall", "f1", "roc_auc", "pr_auc"].map((key) => (
                      <div key={key}><dt>{key}</dt><dd>{formatNumber(v.ground_truth_metrics[key], 3)}</dd></div>
                    ))}
                    <div><dt>Confusion matrix</dt><dd>{JSON.stringify(v.ground_truth_metrics.confusion_matrix)}</dd></div>
                  </dl>
                ) : (
                  <p className="dash-note">
                    Precision, Recall, F1, ROC-AUC и PR-AUC не показываются: модель обучена без размеченной ground truth
                    (unsupervised IsolationForest), измеренных метрик нет.
                  </p>
                )}
              </article>
            );
          })}
          <h4>История детекции</h4>
          {detail.detection_history.length === 0 ? <p className="dash-note">Детекция этой моделью не запускалась.</p> : (
            <DataTable rowKey={(r) => `${r.model_version}:${r.dataset_id}:${r.batch_id}`} rows={detail.detection_history} columns={[
              { key: "model_version", header: "Версия" },
              { key: "dataset_id", header: "Набор", render: (r) => shortId(r.dataset_id) },
              { key: "batch_id", header: "Batch", render: (r) => shortId(r.batch_id) },
              { key: "rows_scored", header: "Строк", align: "right", render: (r) => formatInt(r.rows_scored) },
              { key: "anomaly_count", header: "Аномалий", align: "right", render: (r) => formatInt(r.anomaly_count) },
              { key: "created_at", header: "Когда", render: (r) => formatDate(r.created_at) },
            ]} />
          )}
        </>
      )}
    </ChartCard>
  );
}

export default function MLAnalyticsDashboard() {
  const d = useDashboard();
  const dataset = d.datasetId || d.analyticsDatasetId;
  const overview = useAsync((s) => analytics.mlOverview({ dataset_id: d.datasetId, ...d.period }, s), [d.datasetId, d.dateFrom, d.dateTo]);
  const registry = useAsync((s) => analytics.models(s), []);
  const runs = useAsync((s) => analytics.mlRuns({ limit: 10 }, s), []);
  const drift = useAsync((s) => analytics.drift({ dataset_id: d.datasetId }, s), [d.datasetId]);
  const summary = useAsync((s) => analytics.anomaliesSummary({ dataset_id: dataset }, s), [dataset], Boolean(dataset));
  const catalog = useAsync((s) => analytics.waterCatalog({ dataset_id: dataset }, s), [dataset], Boolean(dataset));

  const [batchPick, setBatchPick] = useState("");
  const [paramPick, setParamPick] = useState("");
  const [paramX, setParamX] = useState("");
  const [paramY, setParamY] = useState("");
  const [station, setStation] = useState("");
  const [offset, setOffset] = useState(0);
  const [model, setModel] = useState("");

  const batches = (summary.data?.by_batch ?? []).map((b) => b.key);
  const batch = batches.includes(batchPick) ? batchPick : (batches[0] ?? "");
  const parameters = catalog.data?.parameters ?? [];
  const parameter = parameters.includes(paramPick) ? paramPick : (parameters[0] ?? "");
  const px = parameters.includes(paramX) ? paramX : (parameters[0] ?? "");
  const py = parameters.includes(paramY) ? paramY : (parameters[1] ?? parameters[0] ?? "");
  const stations = (summary.data?.by_station ?? []).map((s) => s.key).filter((k) => k !== "—");
  const activeStation = stations.includes(station) ? station : "";
  const ready = Boolean(dataset && batch && parameter);
  const modelRef = summary.data?.model;
  const scope = { dataset_id: dataset, batch_id: batch, station_id: activeStation, model_name: modelRef?.model_name, model_version: modelRef?.model_version };

  const series = useAsync((s) => analytics.anomalySeries({ ...scope, parameter }, s), [dataset, batch, parameter, activeStation, modelRef?.model_version], ready);
  const scatter = useAsync((s) => analytics.anomalyScatter({ ...scope, parameter_x: px, parameter_y: py }, s),
    [dataset, batch, px, py, activeStation, modelRef?.model_version], ready && parameters.length > 1);
  const records = useAsync((s) => analytics.anomalyRecords({ ...scope, limit: PAGE, offset }, s),
    [dataset, batch, activeStation, offset, modelRef?.model_version], ready);

  const ov = overview.data;
  const noPredictions = ov && ov.rows_scored === 0;

  const seriesOption = useMemo(() => series.data && scatterOption({
    timeX: series.data.x_kind === "time", xName: series.data.x_kind === "time" ? undefined : "Номер строки", yName: parameter,
    series: [
      { name: "Норма", color: "#22d3ee", line: true, size: 3, data: series.data.normal.map((p) => [p.x, p.value]), opacity: 0.8 },
      { name: "Аномалия", color: "#fb7185", size: 11, z: 5, data: series.data.anomalies.map((p) => [p.x, p.value]) },
    ],
  }), [series.data, parameter]);

  const scatterOpt = useMemo(() => scatter.data && scatterOption({
    xName: px, yName: py,
    series: [
      { name: "Норма", color: "#22d3ee", size: 5, opacity: 0.55, data: scatter.data.normal.map((p) => [p.x, p.y]) },
      { name: "Аномалия", color: "#fb7185", size: 10, z: 5, data: scatter.data.anomalies.map((p) => [p.x, p.y]) },
    ],
  }), [scatter.data, px, py]);

  const hist = summary.data?.score_histogram;
  const histOption = useMemo(() => hist && histogramOption({
    edges: hist.edges, xName: "anomaly_score (ниже — аномальнее)",
    series: [{ name: "Норма", data: hist.normal, color: "#22d3ee" }, { name: "Аномалия", data: hist.anomaly, color: "#fb7185" }],
  }), [hist]);

  const byStation = useMemo(() => barOption({
    categories: (summary.data?.by_station ?? []).map((s) => s.key),
    series: [{ name: "Аномалии", data: (summary.data?.by_station ?? []).map((s) => s.anomalies), color: "#fb7185" }],
    yName: "шт.", legend: false,
  }), [summary.data]);

  const byParam = useMemo(() => {
    const totals = {};
    (summary.data?.by_feature ?? []).forEach((f) => { totals[f.parameter] = (totals[f.parameter] ?? 0) + f.anomalies; });
    const entries = Object.entries(totals).sort((a, b) => b[1] - a[1]);
    return barOption({ categories: entries.map((e) => e[0]), series: [{ name: "Аномалии", data: entries.map((e) => e[1]), color: "#fbbf24" }], yName: "шт.", legend: false });
  }, [summary.data]);

  const latest = drift.data?.latest;
  const psiBars = useMemo(() => {
    const entries = Object.entries(latest?.feature_drift ?? {}).filter(([, v]) => v.psi != null).sort((a, b) => b[1].psi - a[1].psi);
    return barOption({
      categories: entries.map((e) => e[0]),
      series: [{ name: "PSI", data: entries.map((e) => e[1].psi), color: "#a78bfa" }],
      yName: "PSI", horizontal: true, legend: false,
    });
  }, [latest]);
  const psiTrend = useMemo(() => lineOption({
    categories: (drift.data?.reports ?? []).map((r) => formatDate(r.generated_at)),
    series: [{ name: "Максимальный PSI", data: (drift.data?.reports ?? []).map((r) => r.max_psi) }],
    yName: "PSI", zoom: false,
    markLines: drift.data ? [{ name: `warning ${drift.data.thresholds.warning}`, value: drift.data.thresholds.warning },
      { name: `alert ${drift.data.thresholds.alert}`, value: drift.data.thresholds.alert }] : [],
  }), [drift.data]);

  const refresh = () => [overview, registry, runs, drift, summary, series, scatter, records].forEach((s) => s.reload());

  return (
    <div className="dash">
      <DashboardHeader title="ML & Anomaly Detection" subtitle="Реальные результаты детекции, реестр моделей и мониторинг дрейфа"
        updatedAt={overview.updatedAt} onRefresh={refresh} loading={overview.loading}>
        <CommonFilters />
      </DashboardHeader>

      {overview.error ? <ChartCard title="Anomaly Detection Overview" state={overview} /> : (
        <div className="kpi-grid">
          {overview.loading ? Array.from({ length: 6 }, (_, i) => <div key={i} className="kpi-card skeleton-card" aria-hidden="true" />) : (
            <>
              <KpiCard label="Total Anomalies" value={noPredictions ? null : ov.anomalies} description="Записи, помеченные детектором" />
              <KpiCard label="Normal Observations" value={noPredictions ? null : ov.normal} description="Оценённые записи без аномалии" />
              <KpiCard label="Anomaly Rate" display={formatPercent(ov.anomaly_rate, 2)} description="Аномалии / оценённые записи" />
              <KpiCard label="Models Used" value={ov.models_used.length} description="Модель + версия среди сохранённых предсказаний" />
              <KpiCard label="Last Detection" display={formatDate(ov.last_detection_at)} description="Время последних сохранённых предсказаний" />
              <KpiCard label="Detection Status" display={ov.last_run?.status ?? "N/A"} description={ov.last_run ? `Запуск ${shortId(ov.last_run.run_id)}` : "Запусков inference не зафиксировано"} />
            </>
          )}
        </div>
      )}
      {noPredictions && (
        <ChartCard title="Нет результатов детекции" state={{ loading: false, error: null }} isEmpty
          emptyHint="Для выбранной области нет сохранённых предсказаний. Обучите модель и запустите inference (POST /api/v1/ml/inference или DAG ekover_ml)." />
      )}

      {catalog.error && <ChartCard title="Параметры набора данных" state={catalog} />}
      {!noPredictions && ready && (
        <>
          <ChartCard title="Anomaly Detection" state={summary} className="span-2"
            description={modelRef ? `Модель ${modelRef.model_name} ${modelRef.model_version}. ${summary.data.score_note}` : undefined}
            actions={(
              <>
                <SelectField label="Batch" value={batch} options={batches.map((b) => ({ value: b, label: shortId(b) }))} onChange={(v) => { setBatchPick(v); setOffset(0); }} />
                <SelectField label="Параметр" value={parameter} options={parameters.map((p) => ({ value: p, label: p }))} onChange={setParamPick} />
                <SelectField label="Станция" value={activeStation} placeholder="Все" options={stations.map((s) => ({ value: s, label: s }))} onChange={(v) => { setStation(v); setOffset(0); }} />
              </>
            )}>
            <p className="dash-note">Оценка модели — это только сохранённый результат inference; без ground truth качество детекции не измеряется.</p>
          </ChartCard>

          <ChartCard title="Time Series with Anomaly Markers" description={`${parameter}: красные точки — аномалии`} state={series}
            isEmpty={series.data && series.data.total_points === 0} className="span-2">
            {seriesOption && <EChart option={seriesOption} height={340} label="Временной ряд с аномалиями" />}
            {series.data?.downsampled && <p className="dash-note">Нормальные точки прорежены для отображения; аномалии показаны все.</p>}
          </ChartCard>

          <div className="dash-grid">
            <ChartCard title="Scatter Plot" state={parameters.length > 1 ? scatter : { loading: false, error: null }} isEmpty={parameters.length < 2}
              emptyHint="Для scatter нужно минимум два параметра"
              actions={(
                <>
                  <SelectField label="X" value={px} options={parameters.map((p) => ({ value: p, label: p }))} onChange={setParamX} />
                  <SelectField label="Y" value={py} options={parameters.map((p) => ({ value: p, label: p }))} onChange={setParamY} />
                </>
              )}>
              {scatterOpt && <EChart option={scatterOpt} height={300} label="Scatter норма и аномалии" />}
            </ChartCard>
            <ChartCard title="Normal vs Anomaly Distribution" description="Распределение anomaly_score одной модели" state={summary} isEmpty={!hist}>
              {histOption && <EChart option={histOption} height={300} label="Распределение score" />}
            </ChartCard>
            <ChartCard title="Anomalies by Station" state={summary} isEmpty={!summary.data?.by_station.length || (summary.data.by_station.length === 1 && summary.data.by_station[0].key === "—")}
              emptyHint="В наборе данных нет колонки станции">
              <EChart option={byStation} height={260} label="Аномалии по станциям" />
            </ChartCard>
            <ChartCard title="Anomalies by Parameter" description="Параметр с наибольшим отклонением у аномальной записи (top-1)" state={summary} isEmpty={!summary.data?.by_feature.length}>
              <EChart option={byParam} height={260} label="Аномалии по параметрам" />
            </ChartCard>
          </div>

          <ChartCard title="Аномальные записи" state={records} isEmpty={records.data && records.data.total === 0} className="span-2"
            emptyHint="Аномалий не обнаружено">
            {records.data && (
              <DataTable rowKey={(r) => r.prediction_id} rows={records.data.items} page={{ limit: PAGE, offset, total: records.data.total }} onPage={setOffset}
                columns={[
                  { key: "measured_at", header: "Дата", render: (r) => (r.measured_at ? formatDate(r.measured_at) : `строка ${r.row_number ?? "—"}`) },
                  { key: "station_id", header: "Станция" },
                  ...records.data.parameters.map((name) => ({ key: name, header: name, align: "right", render: (r) => formatNumber(r.values[name], 3) })),
                  { key: "anomaly_score", header: "Score", align: "right", render: (r) => formatNumber(r.anomaly_score, 4) },
                  { key: "top_feature", header: "Главный признак", render: (r) => r.top_feature?.feature ?? "—" },
                  { key: "model", header: "Модель", render: (r) => `${r.model_name} ${r.model_version}` },
                ]} />
            )}
          </ChartCard>
        </>
      )}

      <ChartCard title="Model Registry" description="Файловый реестр моделей (candidate → staging → production → archived)" state={registry}
        isEmpty={registry.data && registry.data.length === 0} emptyHint="Обученных моделей пока нет" className="span-2">
        <DataTable rowKey={(r) => r.model_name} rows={registry.data ?? []} selectedKey={model} onRowClick={(r) => setModel(r.model_name)}
          columns={[
            { key: "model_name", header: "Модель", sortable: true },
            { key: "latest_version", header: "Последняя версия" },
            { key: "production_version", header: "Активная (production)", render: (r) => r.production_version ?? "не назначена" },
            { key: "versions", header: "Версий", align: "right", render: (r) => r.versions.length },
            { key: "latest_status", header: "Статус последней", render: (r) => <StatusBadge value={r.versions[r.versions.length - 1].status} /> },
          ]} />
      </ChartCard>
      {model && <ModelCard name={model} onClose={() => setModel("")} />}

      <div className="dash-grid">
        <ChartCard title="Drift Monitoring" state={drift} isEmpty={drift.data && !drift.data.available}
          emptyHint="Отчёты о дрейфе не формировались. Они создаются шагом monitor DAG ekover_ml."
          description={drift.data ? `Пороги PSI: warning ${drift.data.thresholds.warning}, alert ${drift.data.thresholds.alert} (backend/ml/monitoring.py)` : undefined}>
          {latest && (
            <>
              <p>Статус: <StatusBadge value={latest.overall_status} /> · модель {latest.model_name} {latest.model_version} · batch {shortId(latest.batch_id)}</p>
              <EChart option={psiBars} height={Math.max(200, Object.keys(latest.feature_drift).length * 26 + 60)} label="PSI по признакам" />
              <p className="dash-note">Признаки с дрейфом: {latest.drifted_features.join(", ") || "нет"}.</p>
            </>
          )}
        </ChartCard>
        <ChartCard title="PSI Trend" state={drift} isEmpty={!drift.data?.available}
          description="Максимальный PSI по признакам в каждом отчёте" emptyHint="Нет отчётов о дрейфе">
          <EChart option={psiTrend} height={260} label="Тренд PSI" />
          {drift.data?.reports.some((r) => r.generated_at_source === "file_mtime") && (
            <p className="dash-note">У части отчётов нет времени генерации — использовано время изменения файла.</p>
          )}
        </ChartCard>
      </div>

      <ChartCard title="Запуски обучения и inference" state={runs} isEmpty={runs.data && runs.data.items.length === 0}
        emptyHint="Запусков пока не было" className="span-2">
        <DataTable rowKey={(r) => r.run_id} rows={runs.data?.items ?? []} columns={[
          { key: "kind", header: "Тип" },
          { key: "model_name", header: "Модель" },
          { key: "status", header: "Статус", render: (r) => <StatusBadge value={r.status} /> },
          { key: "started_at", header: "Начало", render: (r) => formatDate(r.started_at) },
          { key: "finished_at", header: "Конец", render: (r) => formatDate(r.finished_at) },
          { key: "error", header: "Ошибка", render: (r) => r.error ?? "—" },
        ]} />
      </ChartCard>
    </div>
  );
}
