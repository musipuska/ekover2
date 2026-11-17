const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

function makeQuery(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function request(url, options = {}) {
  const response = await fetch(`${API_URL}${url}`, options);

  let result = {};

  try {
    result = await response.json();
  } catch {
    if (response.ok) {
      return null;
    }
  }

  if (!response.ok) {
    const message =
      result?.error?.message ||
      result?.detail?.message ||
      result?.detail ||
      result?.message ||
      `Ошибка сервера: ${response.status}`;

    throw new Error(
      typeof message === "string" ? message : JSON.stringify(message)
    );
  }

  // Новый формат ответов ЭКОВЕР:
  // { status: "success", data: ..., metadata: ... }
  if (
    result &&
    result.status === "success" &&
    Object.prototype.hasOwnProperty.call(result, "data")
  ) {
    return result.data;
  }

  return result;
}

async function postJson(url, body) {
  return request(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export const api = {
  // -----------------------------
  // Наборы данных
  // -----------------------------

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

  // -----------------------------
  // Аналитика
  // -----------------------------

  getAnalyticsOverview() {
    return request("/analytics/overview");
  },

  getAnalyticsDatasets(params = {}) {
    return request(`/analytics/datasets${makeQuery(params)}`);
  },

  getParameterMetrics(datasetId, batchId) {
    return request(
      `/analytics/datasets/${encodeURIComponent(datasetId)}/parameters${makeQuery({
        batch_id: batchId,
      })}`
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

  // -----------------------------
  // Машинное обучение
  // -----------------------------

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

  startTraining(body) {
    return postJson("/ml/training-runs", body);
  },

  startInference(body) {
    return postJson("/ml/inference", body);
  },

  getMLRun(runId) {
    return request(`/ml/runs/${encodeURIComponent(runId)}`);
  },

  // Этот метод заработает после добавления GET /ml/runs на backend.
  getMLRuns(params = {}) {
    return request(`/ml/runs${makeQuery(params)}`);
  },

  getPredictions(params = {}) {
    return request(`/ml/predictions${makeQuery(params)}`);
  },

  getAnomalies(params = {}) {
    return request(`/ml/anomalies${makeQuery(params)}`);
  },

  getMLAnalytics(params = {}) {
    return request(`/ml/analytics${makeQuery(params)}`);
  },

  getAnomaly(predictionId) {
    return request(
      `/ml/anomalies/${encodeURIComponent(predictionId)}`
    );
  },
};