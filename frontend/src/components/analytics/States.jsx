import { AlertCircle, Inbox, RefreshCw } from "lucide-react";

export function LoadingState({ height = 160 }) {
  return (
    <div className="skeleton" style={{ height }} role="status" aria-label="Загрузка данных">
      <span className="skeleton-bar" />
      <span className="skeleton-bar short" />
      <span className="skeleton-bar" />
    </div>
  );
}

export function EmptyState({ title = "Нет данных", hint }) {
  return (
    <div className="dash-empty">
      <Inbox size={28} />
      <strong>{title}</strong>
      {hint && <span>{hint}</span>}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="dash-error" role="alert">
      <AlertCircle size={22} />
      <div>
        <strong>Не удалось загрузить данные</strong>
        <span>{error?.message ?? "Неизвестная ошибка"}</span>
      </div>
      {onRetry && (
        <button type="button" className="dash-button" onClick={onRetry}>
          <RefreshCw size={14} /> Повторить
        </button>
      )}
    </div>
  );
}
