import { useMemo, useState } from "react";

import { DashboardContext } from "./DashboardContext";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import { analytics } from "../services/analyticsApi";

/**
 * Общие фильтры дашбордов (набор данных и период) живут выше страниц,
 * поэтому не теряются при переключении разделов.
 */
export default function DashboardProvider({ children, navigate, navParams }) {
  const [datasetId, setDatasetId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const datasetsState = useAsync(async (signal) => ({ data: await api.getDatasets(signal), meta: {} }), []);
  const martsState = useAsync((signal) => analytics.martsDatasets({}, signal), []);

  const value = useMemo(() => {
    const datasets = Array.isArray(datasetsState.data) ? datasetsState.data : [];
    const marts = martsState.data ?? [];
    const withMarts = [...new Set(marts.map((item) => item.dataset_id))];
    const names = Object.fromEntries(datasets.map((item) => [item.id, item.name || item.id]));
    // Для water/ML нужны витрины: если выбранного набора в них нет, берём последний опубликованный.
    const analyticsDatasetId = withMarts.includes(datasetId) ? datasetId : (withMarts[0] ?? "");
    return {
      datasetId, setDatasetId,
      dateFrom, setDateFrom,
      dateTo, setDateTo,
      datasets, withMarts, names,
      analyticsDatasetId,
      datasetsLoading: datasetsState.loading || martsState.loading,
      datasetName: (id) => names[id] ?? id,
      period: { date_from: dateFrom || undefined, date_to: dateTo || undefined },
      navigate, navParams: navParams ?? {},
      resetFilters: () => { setDatasetId(""); setDateFrom(""); setDateTo(""); },
    };
  }, [datasetId, dateFrom, dateTo, datasetsState.data, datasetsState.loading, martsState.data, martsState.loading,
    navigate, navParams]);

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}
