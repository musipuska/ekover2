const API_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, { status = 0, code = null, details = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function messageFromBody(body, fallback) {
  if (!body) return fallback;
  if (body.error?.message) return body.error.message;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail) && body.detail.length) {
    return body.detail
      .map((item) => `${(item.loc || []).slice(1).join(".")}: ${item.msg}`)
      .join("; ");
  }
  return fallback;
}

export function buildQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.append(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export async function request(url, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${url}`, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("Не удалось связаться с сервером. Проверьте, что backend запущен.", {
      code: "NETWORK_ERROR",
    });
  }

  if (!response.ok) {
    let body = null;
    try {
      body = await response.json();
    } catch {
      // тело ответа не JSON — остаётся сообщение по умолчанию
    }
    throw new ApiError(messageFromBody(body, `Ошибка сервера: ${response.status}`), {
      status: response.status,
      code: body?.error?.code ?? null,
      details: body?.error?.details ?? null,
    });
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
