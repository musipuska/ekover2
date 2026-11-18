import { useDashboard } from "../../hooks/useDashboard";

export function Field({ label, children }) {
  return (
    <label className="filter-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function SelectField({ label, value, onChange, options, placeholder }) {
  return (
    <Field label={label}>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </Field>
  );
}

/** Общие фильтры: набор данных и период. `onlyWithMarts` — для разделов, которым нужны аналитические витрины. */
export function CommonFilters({ onlyWithMarts = false, withDataset = true, withPeriod = true }) {
  const d = useDashboard();
  const ids = onlyWithMarts ? d.withMarts : d.datasets.map((item) => item.id);
  const options = ids.map((id) => ({ value: id, label: d.datasetName(id) }));
  return (
    <>
      {withDataset && (
        <SelectField
          label="Набор данных"
          value={onlyWithMarts ? d.analyticsDatasetId : d.datasetId}
          onChange={d.setDatasetId}
          options={options}
          placeholder={onlyWithMarts ? undefined : "Все наборы"}
        />
      )}
      {withPeriod && (
        <>
          <Field label="С даты">
            <input type="date" value={d.dateFrom} max={d.dateTo || undefined} onChange={(e) => d.setDateFrom(e.target.value)} />
          </Field>
          <Field label="По дату">
            <input type="date" value={d.dateTo} min={d.dateFrom || undefined} onChange={(e) => d.setDateTo(e.target.value)} />
          </Field>
        </>
      )}
      {(d.dateFrom || d.dateTo || d.datasetId) && (
        <button type="button" className="dash-button ghost" onClick={d.resetFilters}>Сбросить</button>
      )}
    </>
  );
}
