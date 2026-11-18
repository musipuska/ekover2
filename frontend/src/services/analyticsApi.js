import { buildQuery, request } from "./api";

async function get(path, params, signal) {
  const body = await request(`${path}${buildQuery(params)}`, { signal });
  return { data: body.data, meta: body.metadata ?? {} };
}

const A = "/analytics";

export const analytics = {
  // --- общие ---------------------------------------------------------------
  summary: (p, s) => get(`${A}/summary`, p, s),
  martsDatasets: (p, s) => get(`${A}/datasets`, { limit: 500, ...p }, s),
  trends: (datasetId, p, s) => get(`${A}/datasets/${encodeURIComponent(datasetId)}/trends`, p, s),
  stationMetrics: (datasetId, p, s) => get(`${A}/datasets/${encodeURIComponent(datasetId)}/stations`, p, s),

  // --- Water Quality ---------------------------------------------------------
  waterCatalog: (p, s) => get(`${A}/water/catalog`, p, s),
  distribution: (p, s) => get(`${A}/water/distribution`, p, s),
  correlation: (p, s) => get(`${A}/water/correlation`, p, s),
  thresholds: (s) => get(`${A}/water/thresholds`, {}, s),
  measurements: (p, s) => get(`${A}/water/measurements`, p, s),

  // --- Data Quality ------------------------------------------------------------
  qualityOverview: (p, s) => get(`${A}/quality/overview`, p, s),
  qualityRules: (p, s) => get(`${A}/quality/rules`, p, s),
  qualityColumns: (p, s) => get(`${A}/quality/columns`, p, s),

  // --- ML ------------------------------------------------------------------------
  mlOverview: (p, s) => get(`${A}/ml/overview`, p, s),
  anomaliesSummary: (p, s) => get(`${A}/ml/anomalies/summary`, p, s),
  anomalySeries: (p, s) => get(`${A}/ml/anomalies/series`, p, s),
  anomalyScatter: (p, s) => get(`${A}/ml/anomalies/scatter`, p, s),
  anomalyRecords: (p, s) => get(`${A}/ml/anomalies/records`, p, s),
  modelDetail: (name, s) => get(`${A}/ml/models/${encodeURIComponent(name)}`, {}, s),
  mlRuns: (p, s) => get(`${A}/ml/runs`, p, s),
  drift: (p, s) => get(`${A}/ml/drift`, p, s),
  models: (s) => get("/ml/models", {}, s),

  // --- ETL & Pipeline --------------------------------------------------------------
  pipelineOverview: (p, s) => get(`${A}/pipeline/overview`, p, s),
  pipelinePerformance: (p, s) => get(`${A}/pipeline/performance`, p, s),
  pipelineJobs: (p, s) => get(`${A}/pipeline/jobs`, p, s),
  pipelineJob: (jobId, s) => get(`${A}/pipeline/jobs/${encodeURIComponent(jobId)}`, {}, s),
  pipelineErrors: (p, s) => get(`${A}/pipeline/errors`, p, s),
};
