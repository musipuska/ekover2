import { useMemo, useState } from "react";

import ChartCard from "../components/analytics/ChartCard";
import DashboardHeader from "../components/analytics/DashboardHeader";
import { CommonFilters, Field, SelectField } from "../components/analytics/DashboardFilters";
import DataTable from "../components/analytics/DataTable";
import EChart from "../components/charts/EChart";
import { barOption, boxplotOption, heatmapOption, histogramOption, lineOption } from "../components/charts/options";
import { EmptyState } from "../components/analytics/States";
import { useAsync } from "../hooks/useAsync";
import { useDashboard } from "../hooks/useDashboard";
import { analytics } from "../services/analyticsApi";
import { formatDate, formatInt, formatNumber } from "../utils/format";
import { aggregateTrends } from "../utils/series";

const GRAINS = [{ value: "day", label: "День" }, { value: "week", label: "Неделя" }, { value: "month", label: "Месяц" }];
const PERCENTILE_LABELS = { p01: "P1", p05: "P5", p25: "P25", median: "Медиана", p75: "P75", p95: "P95", p99: "P99" };
const PAGE = 10;

export default function WaterQualityDashboard() {
  const d = useDashboard();
  const dataset = d.analyticsDatasetId;
  const enabled = Boolean(dataset);

  const [chosen, setChosen] = useState("");
  const [station, setStation] = useState("");
  const [compare, setCompare] = useState([]);
  const [grain, setGrain] = useState("day");
  const [method, setMethod] = useState("pearson");
  const [offset, setOffset] = useState(0);

  const catalog = useAsync((s) => analytics.waterCatalog({ dataset_id: dataset }, s), [dataset], enabled);
  const parameters = catalog.data?.parameters ?? [];
  const stations = catalog.data?.stations ?? [];
  const parameter = parameters.includes(chosen) ? chosen : (parameters[0] ?? "");
  const activeStation = stations.includes(station) ? station : "";
  const ready = enabled && Boolean(parameter);
  const scope = { dataset_id: dataset, parameter, station_id: activeStation, ...d.period };
  const deps = [dataset, parameter, activeStation, d.dateFrom, d.dateTo];

  const thresholds = useAsync((s) => analytics.thresholds(s), []);
  const trends = useAsync((s) => analytics.trends(dataset, { parameter, limit: 10000, ...d.period }, s),
    [dataset, parameter, d.dateFrom, d.dateTo], ready);
  const stationStats = useAsync((s) => analytics.stationMetrics(dataset, { parameter }, s), [dataset, parameter], ready);
  const distribution = useAsync((s) => analytics.distribution(scope, s), deps, ready);
  const correlation = useAsync((s) => analytics.correlation({ dataset_id: dataset, station_id: activeStation, method, ...d.period }, s),
    [dataset, activeStation, method, d.dateFrom, d.dateTo], enabled);
  const measurements = useAsync((s) => analytics.measurements({ ...scope, limit: PAGE, offset }, s), [...deps, offset], ready);

  const limit = thresholds.data?.items.find((t) => t.parameter === parameter);

  // --- временной ряд -------------------------------------------------------------
  const grouped = useMemo(() => aggregateTrends(trends.data ?? [], grain), [trends.data, grain]);
  const trendOption = useMemo(() => {
    const keys = [...new Set(Object.values(grouped).flat().map((p) => p.key))].sort();
    const lookup = (name) => {
      const byKey = new Map((grouped[name] ?? []).map((p) => [p.key, p.avg]));
      return keys.map((key) => byKey.get(key) ?? null);
    };
    const names = compare.length ? compare.filter((s) => grouped[s]) : ["__all__"];
    const marks = [];
    if (limit?.min != null) marks.push({ name: "мин. допустимое (quality gate)", value: limit.min });
    if (limit?.max != null) marks.push({ name: "макс. допустимое (quality gate)", value: limit.max });
    return lineOption({
      categories: keys,
      series: names.map((name) => ({ name: name === "__all__" ? "Все станции" : name, data: lookup(name) })),
      yName: parameter, markLines: marks,
    });
  }, [grouped, compare, limit, parameter]);

  // --- станции ------------------------------------------------------------------------
  const rows = useMemo(() => [...(stationStats.data ?? [])].sort((a, b) => (b.avg_value ?? -Infinity) - (a.avg_value ?? -Infinity)), [stationStats.data]);
  const stationBar = useMemo(() => barOption({
    categories: rows.map((r) => r.station_id),
    series: [{ name: "Среднее", data: rows.map((r) => r.avg_value) }],
    yName: parameter, legend: false,
  }), [rows, parameter]);
  const stationGrouped = useMemo(() => barOption({
    categories: rows.map((r) => r.station_id),
    series: [
      { name: "Мин", data: rows.map((r) => r.min_value) },
      { name: "Медиана", data: rows.map((r) => r.median_value) },
      { name: "Среднее", data: rows.map((r) => r.avg_value) },
      { name: "Макс", data: rows.map((r) => r.max_value) },
    ],
    yName: parameter,
  }), [rows, parameter]);

  // --- распределение --------------------------------------------------------------------
  const dist = distribution.data;
  const histogram = useMemo(() => dist?.histogram && histogramOption({
    edges: dist.histogram.edges, series: [{ name: "Измерений", data: dist.histogram.counts }], xName: parameter,
  }), [dist, parameter]);
  const box = useMemo(() => dist?.boxplot && boxplotOption({ box: dist.boxplot, name: parameter, unit: parameter }), [dist, parameter]);

  const corr = correlation.data;
  const heat = useMemo(() => corr && heatmapOption({ labels: corr.parameters, matrix: corr.matrix }), [corr]);

  const toggleCompare = (name) => setCompare((list) => (list.includes(name) ? list.filter((s) => s !== name) : [...list, name].slice(-6)));
  const catalogState = enabled ? catalog : { loading: d.datasetsLoading, error: null };
  const refresh = () => [catalog, trends, stationStats, distribution, correlation, measurements].forEach((s) => s.reload());

  return (
    <div className="dash">
      <DashboardHeader title="Water Quality Analytics" subtitle="Показатели, станции, распределения и связи между параметрами"
        updatedAt={distribution.updatedAt ?? catalog.updatedAt} onRefresh={refresh} loading={catalog.loading || distribution.loading}>
        <CommonFilters onlyWithMarts />
        <SelectField label="Параметр" value={parameter} onChange={(v) => { setChosen(v); setOffset(0); }}
          options={parameters.map((p) => ({ value: p, label: p }))} />
        <SelectField label="Станция" value={activeStation} placeholder="Все станции" onChange={(v) => { setStation(v); setOffset(0); }}
          options={stations.map((s) => ({ value: s, label: s }))} />
        <SelectField label="Агрегация" value={grain} onChange={setGrain} options={GRAINS} />
      </DashboardHeader>

      {!enabled && !catalogState.loading && (
        <ChartCard title="Аналитика" state={catalogState} isEmpty emptyHint="Нет наборов данных с построенными витринами. Загрузите CSV и дождитесь завершения обработки." />
      )}
      {catalog.error && <ChartCard title="Каталог параметров" state={catalog} />}

      {ready && (
        <>
          <ChartCard title="Динамика показателя" state={trends} isEmpty={!Object.keys(grouped).length}
            emptyHint="Нет измерений за выбранный период или в наборе нет колонки времени"
            description={`${parameter} · среднее с взвешиванием по числу измерений${limit ? " · пунктир — допустимый диапазон из quality gate (не санитарная норма)" : ""}`}
            actions={stations.length > 1 && (
              <Field label="Сравнить станции">
                <span className="chips">
                  {stations.map((name) => (
                    <label key={name} className={`chip ${compare.includes(name) ? "on" : ""}`}>
                      <input type="checkbox" checked={compare.includes(name)} onChange={() => toggleCompare(name)} /> {name}
                    </label>
                  ))}
                </span>
              </Field>
            )} className="span-2">
            <EChart option={trendOption} height={340} label={`Временной ряд ${parameter}`} />
            {trends.data && trends.meta?.total > 10000 && <p className="dash-note">Показаны первые 10 000 дневных записей.</p>}
          </ChartCard>

          <div className="dash-grid">
            <ChartCard title="Сравнение станций" description="Весь batch, период не применяется (витрина station_metrics)" state={stationStats}
              isEmpty={!rows.length} emptyHint="В наборе данных нет колонки станции">
              <EChart option={stationBar} height={260} label="Среднее по станциям" />
            </ChartCard>
            <ChartCard title="Мин / медиана / среднее / макс" state={stationStats} isEmpty={!rows.length} emptyHint="В наборе данных нет колонки станции">
              <EChart option={stationGrouped} height={260} label="Статистики по станциям" />
            </ChartCard>
          </div>
          <ChartCard title="Station Ranking" description="По среднему значению, по убыванию" state={stationStats} isEmpty={!rows.length}
            emptyHint="В наборе данных нет колонки станции" className="span-2">
            <DataTable rowKey={(r) => r.station_id} rows={rows} columns={[
              { key: "rank", header: "#", render: (r) => rows.indexOf(r) + 1 },
              { key: "station_id", header: "Станция", sortable: true },
              { key: "avg_value", header: "Среднее", align: "right", sortable: true, render: (r) => formatNumber(r.avg_value, 3) },
              { key: "median_value", header: "Медиана", align: "right", sortable: true, render: (r) => formatNumber(r.median_value, 3) },
              { key: "min_value", header: "Мин", align: "right", sortable: true, render: (r) => formatNumber(r.min_value, 3) },
              { key: "max_value", header: "Макс", align: "right", sortable: true, render: (r) => formatNumber(r.max_value, 3) },
              { key: "std_value", header: "Ст. откл.", align: "right", sortable: true, render: (r) => formatNumber(r.std_value, 3) },
              { key: "measurement_count", header: "Измерений", align: "right", sortable: true, render: (r) => formatInt(r.measurement_count) },
            ]} />
          </ChartCard>

          <div className="dash-grid">
            <ChartCard title="Распределение" description={`${parameter}${activeStation ? ` · станция ${activeStation}` : ""}`}
              state={distribution} isEmpty={dist && dist.n === 0} emptyHint="Нет значений параметра в выбранной области">
              {histogram && <EChart option={histogram} height={260} label="Гистограмма" />}
            </ChartCard>
            <ChartCard title="Box Plot" description="Усы — 1.5 IQR, точки — выбросы" state={distribution} isEmpty={dist && dist.n === 0}>
              {box && <EChart option={box} height={260} label="Box plot" />}
            </ChartCard>
          </div>
          <ChartCard title="Distribution Summary" state={distribution} isEmpty={dist && dist.n === 0}>
            {dist?.summary && (
              <>
                <dl className="summary-grid">
                  <div><dt>Измерений</dt><dd>{formatInt(dist.n)}</dd></div>
                  <div><dt>Пропусков</dt><dd>{formatInt(dist.null_count)}</dd></div>
                  <div><dt>Среднее</dt><dd>{formatNumber(dist.summary.mean, 3)}</dd></div>
                  <div><dt>Ст. отклонение</dt><dd>{formatNumber(dist.summary.std, 3)}</dd></div>
                  <div><dt>Мин</dt><dd>{formatNumber(dist.summary.min, 3)}</dd></div>
                  <div><dt>Макс</dt><dd>{formatNumber(dist.summary.max, 3)}</dd></div>
                  {Object.entries(dist.percentiles).map(([key, value]) => (
                    <div key={key}><dt>{PERCENTILE_LABELS[key] ?? key}</dt><dd>{formatNumber(value, 3)}</dd></div>
                  ))}
                </dl>
                {dist.threshold ? (
                  <p className="dash-note" data-testid="threshold-note">
                    Допустимый диапазон (quality gate «{dist.threshold.rule}»): {dist.threshold.min ?? "−∞"} … {dist.threshold.max ?? "+∞"}.
                    Ниже: {formatInt(dist.threshold.below)}, выше: {formatInt(dist.threshold.above)}. {dist.threshold.description}
                  </p>
                ) : <p className="dash-note">Для этого параметра в конфигурации нет допустимого диапазона; нормативы качества воды не настроены.</p>}
              </>
            )}
          </ChartCard>

          <ChartCard title="Корреляции параметров" state={correlation} isEmpty={corr && corr.parameters.length < 2}
            emptyHint="Для корреляции нужно минимум два числовых параметра"
            description={corr?.note}
            actions={<SelectField label="Метод" value={method} onChange={setMethod}
              options={[{ value: "pearson", label: "Pearson" }, { value: "spearman", label: "Spearman" }]} />} className="span-2">
            {heat && <EChart option={heat} height={Math.max(300, corr.parameters.length * 44 + 120)} label="Матрица корреляций" />}
            {corr?.truncated && <p className="dash-note">Показаны параметры с наибольшим числом значений.</p>}
          </ChartCard>

          <ChartCard title="Измерения" description="Исходные значения из Gold с отметкой выхода за допустимый диапазон" state={measurements}
            isEmpty={measurements.data && measurements.data.items.length === 0 && offset === 0}
            emptyHint="Нет измерений в выбранной области" className="span-2"
            actions={<button type="button" className="dash-button ghost" onClick={() => d.navigate("datasets")}>Перейти к набору данных</button>}>
            {measurements.data && (
              <DataTable rowKey={(r) => `${r.row_number}-${r.measured_at}-${r.station_id}`} rows={measurements.data.items}
                page={{ limit: PAGE, offset, total: measurements.meta?.total ?? measurements.data.total }} onPage={setOffset}
                columns={[
                  { key: "row_number", header: "Строка CSV" },
                  { key: "measured_at", header: "Время", render: (r) => formatDate(r.measured_at) },
                  { key: "station_id", header: "Станция" },
                  { key: "value", header: parameter, align: "right", render: (r) => formatNumber(r.value, 3) },
                  { key: "outside_validity_range", header: "Допустимый диапазон",
                    render: (r) => (r.outside_validity_range === null ? "не задан" : r.outside_validity_range ? "вне диапазона" : "в диапазоне") },
                ]} />
            )}
          </ChartCard>
        </>
      )}
      {enabled && catalog.data && parameters.length === 0 && <EmptyState hint="В наборе данных нет числовых параметров" />}
    </div>
  );
}
