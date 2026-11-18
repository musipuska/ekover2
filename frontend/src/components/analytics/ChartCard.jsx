import { EmptyState, ErrorState, LoadingState } from "./States";

/**
 * Карточка с единым поведением состояний.
 * `state` — результат useAsync; `isEmpty` и `emptyHint` описывают осмысленное «нет данных».
 */
export default function ChartCard({ title, description, state, isEmpty = false, emptyHint, actions, children, className = "", height }) {
  let body;
  if (state?.error) body = <ErrorState error={state.error} onRetry={state.reload} />;
  else if (state?.loading) body = <LoadingState height={height} />;
  else if (isEmpty) body = <EmptyState hint={emptyHint} />;
  else body = children;

  return (
    <section className={`dash-card ${className}`}>
      <header className="dash-card-head">
        <div>
          <h3>{title}</h3>
          {description && <p>{description}</p>}
        </div>
        {actions && <div className="dash-card-actions">{actions}</div>}
      </header>
      {body}
    </section>
  );
}
