import { formatKpi, formatNumber, NA } from "../../utils/format";

function DeltaLabel({ delta }) {
  if (!delta) return null;
  const sign = delta.change > 0 ? "+" : "";
  const pct = delta.change_pct === null || delta.change_pct === undefined ? "" : ` (${sign}${formatNumber(delta.change_pct, 1)}%)`;
  return (
    <span className="kpi-delta" title={`Предыдущий период: ${delta.previous}`}>
      {sign}{delta.change}{pct} к предыдущему периоду
    </span>
  );
}

export default function KpiCard({ label, value, unit, description, delta, valueKey, display }) {
  const text = display ?? formatKpi(value, valueKey);
  return (
    <article className="kpi-card" title={description}>
      <span className="kpi-label">{label}</span>
      <strong className={`kpi-value ${text === NA ? "is-na" : ""}`}>
        {text}
        {text !== NA && unit && <small>{unit}</small>}
      </strong>
      {description && <span className="kpi-desc">{description}</span>}
      <DeltaLabel delta={delta} />
    </article>
  );
}
