import { RefreshCw } from "lucide-react";

import { formatDate } from "../../utils/format";

export function LastUpdated({ value }) {
  return <span className="last-updated">{value ? `Обновлено: ${formatDate(value)}` : "Обновление данных…"}</span>;
}

export default function DashboardHeader({ title, subtitle, updatedAt, onRefresh, loading, children }) {
  return (
    <header className="dash-header">
      <div className="dash-header-top">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <div className="dash-header-meta">
          <LastUpdated value={updatedAt} />
          {onRefresh && (
            <button type="button" className="dash-button" onClick={onRefresh} disabled={loading}>
              <RefreshCw size={14} className={loading ? "spin" : ""} /> Обновить
            </button>
          )}
        </div>
      </div>
      {children && <div className="dash-filters">{children}</div>}
    </header>
  );
}
