export const NA = "N/A";

const isMissing = (value) =>
  value === null || value === undefined || (typeof value === "number" && !Number.isFinite(value));

export function formatInt(value) {
  return isMissing(value) ? NA : Number(value).toLocaleString("ru-RU");
}

export function formatNumber(value, digits = 2) {
  if (isMissing(value)) return NA;
  return Number(value).toLocaleString("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

/** Принимает долю (0–1) и возвращает проценты. */
export function formatPercent(ratio, digits = 1) {
  return isMissing(ratio) ? NA : `${formatNumber(Number(ratio) * 100, digits)}%`;
}

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("ru-RU");
}

export function formatDay(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString("ru-RU");
}

export function formatDuration(seconds) {
  if (isMissing(seconds)) return NA;
  const value = Number(seconds);
  if (value < 1) return `${Math.round(value * 1000)} мс`;
  if (value < 60) return `${formatNumber(value, 1)} с`;
  const minutes = Math.floor(value / 60);
  return `${minutes} мин ${Math.round(value - minutes * 60)} с`;
}

export function shortId(value) {
  return value ? String(value).slice(0, 8) : "—";
}

export function formatKpi(value, key) {
  if (isMissing(value)) return NA;
  if (key === "quality_score") return formatNumber(value, 3);
  return formatInt(value);
}
