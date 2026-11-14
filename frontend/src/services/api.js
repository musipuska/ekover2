
const API_URL = "http://127.0.0.1:8000/api/v1";

// Формируем query-параметры, пропуская пустые значения.
function makeQuery(params = {}) {
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });

  const result = query.toString();
  return result ? `?${result}` : "";
}

// Общая функция запросов к FastAPI.
async function request(url, options = {}) {
  const response = await fetch(`${API_URL}${url}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });

  let result = null;

  try {
    result = await response.json();
  } catch {
    if (response.ok) return null;
  }

  if (!response.ok) {
    const message =
      result?.error?.message ||
      result?.detail ||
      result?.message ||
      `Ошибка сервера: ${response.status}`;

    throw new Error(message);
  }

  // Новые API-методы используют envelope.py.
  // Старые маршруты могут возвращать обычный JSON.
  if (
    result &&
    result.status === "success" &&
    Object.prototype.hasOwnProperty.call(result, "data")
  ) {
    return result.data;
  }

  return result;
}

function postJson(url, body) {
  return request(url, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export const api = {
  // ==========================================
  // НАБОРЫ ДАННЫХ
  // ==========================================

  getDatasets() {
    return request("/datasets");
  },

  getDataset(id) {
    return request(`/datasets/${encodeURIComponent(id)}`);
  },

  uploadDataset(file) {
    const formData = new FormData();
    formData.append("file", file);

    return request("/datasets/uploads", {
      method: "POST",
      body: formData,
    });
  },

  // ==========================================
  // ETL И ОБРАБОТКА
  // ==========================================

  getJob(id) {
    return request(`/jobs/${encodeURIComponent(id)}`);
  },

  getProfile(id) {
    return request(`/datasets/${encodeURIComponent(id)}/profile`);
  },

  getQuality(datasetId, batchId) {
    return request(
      `/datasets/${encodeURIComponent(datasetId)}/quality/${encodeURIComponent(batchId)}`
    );
  },

  // ==========================================
  // АНАЛИТИКА
  // ==========================================

  getAnalyticsOverview() {
    return request("/analytics/overview");
  },

  getAnalyticsDatasets(params = {}) {
    return request(`/analytics/datasets${makeQuery(params)}`);
  },

  getParameterMetrics(datasetId, batchId) {
    return request(
      `/analytics/datasets/${encodeURIComponent(datasetId)}/parameters${makeQuery({ batch_id: batchId })}`
    );
  },

  getStationMetrics(datasetId, params = {}) {
    return request(
      `/analytics/datasets/${encodeURIComponent(datasetId)}/stations${makeQuery(params)}`
    );
  },

  getTrends(datasetId, params = {}) {
    return request(
      `/analytics/datasets/${encodeURIComponent(datasetId)}/trends${makeQuery(params)}`
    );
  },

  getAnalyticsHistory(datasetId) {
    return request(
      `/analytics/datasets/${encodeURIComponent(datasetId)}/quality`
    );
  },

  // ==========================================
  // МАШИННОЕ ОБУЧЕНИЕ
  // ==========================================

  getModels() {
    return request("/ml/models");
  },

  getModel(modelName) {
    return request(`/ml/models/${encodeURIComponent(modelName)}`);
  },

  changeModelStatus(modelName, version, body) {
    return postJson(
      `/ml/models/${encodeURIComponent(modelName)}/versions/${encodeURIComponent(version)}/status`,
      body
    );
  },

  getPredictions(params = {}) {
    return request(`/ml/predictions${makeQuery(params)}`);
  },

  getAnomalies(params = {}) {
    return request(`/ml/anomalies${makeQuery(params)}`);
  },

  getAnomaly(predictionId) {
    return request(
      `/ml/anomalies/${encodeURIComponent(predictionId)}`
    );
  },

  startTraining(body) {
    return postJson("/ml/training-runs", body);
  },

  startInference(body) {
    return postJson("/ml/inference", body);
  },

  getMLRun(runId) {
    return request(`/ml/runs/${encodeURIComponent(runId)}`);
  },
};
