const LABELS = {
  passed: "PASSED", warning: "WARNING", failed: "FAILED",
  success: "Успешно", running: "Выполняется", queued: "В очереди",
  ok: "OK", alert: "Alert",
  healthy: "Работает штатно", degraded: "Есть проблемы", no_data: "Нет данных",
  candidate: "candidate", staging: "staging", production: "production", archived: "archived",
  not_reached: "Не достигнут", not_run: "Не запускался", skipped: "Пропущено",
  critical: "critical", info: "info",
};

const TONES = {
  passed: "good", success: "good", ok: "good", healthy: "good", production: "good",
  warning: "warn",
  failed: "bad", alert: "bad", degraded: "bad", critical: "bad",
  running: "info", queued: "muted", staging: "info", info: "info",
};

/** Значения статусов берутся из backend как есть; неизвестные показываются без подмены. */
export default function StatusBadge({ value }) {
  if (value === null || value === undefined || value === "") return <span className="badge badge-muted">—</span>;
  const key = String(value).toLowerCase();
  return (
    <span className={`badge badge-${TONES[key] ?? "muted"}`} data-status={key}>
      {LABELS[key] ?? String(value)}
    </span>
  );
}
