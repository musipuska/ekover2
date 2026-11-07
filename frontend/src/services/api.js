
const API_URL = "http://127.0.0.1:8000/api/v1";

async function request(url, options = {}) {
  const response = await fetch(`${API_URL}${url}`, options);

  if (!response.ok) {
    let message = `Ошибка сервера: ${response.status}`;

    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // Оставляем исходное сообщение
    }

    throw new Error(message);
  }

  return response.json();
}

export const api = {
  getDatasets() {
    return request("/datasets");
  },

  getDataset(id) {
    return request(`/datasets/${id}`);
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
    return request(`/jobs/${id}`);
  },

  getProfile(id) {
    return request(`/datasets/${id}/profile`);
  },

  getQuality(datasetId, batchId) {
    return request(`/datasets/${datasetId}/quality/${batchId}`);
  },
};
