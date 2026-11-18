import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, buildQuery } from "./api";
import { analytics } from "./analyticsApi";

const respond = (status, body) =>
  vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body });

afterEach(() => vi.unstubAllGlobals());

describe("buildQuery", () => {
  it("drops empty values and encodes the rest", () => {
    expect(buildQuery({ a: "x y", b: "", c: null, d: undefined, e: 0 })).toBe("?a=x+y&e=0");
    expect(buildQuery({})).toBe("");
  });
});

describe("request errors", () => {
  it("reads the envelope error format", async () => {
    vi.stubGlobal("fetch", respond(422, { status: "error", error: { code: "INVALID_DATE", message: "Неверная дата", details: { field: "date_from" } } }));
    await expect(analytics.summary({})).rejects.toMatchObject({ name: "ApiError", status: 422, code: "INVALID_DATE", message: "Неверная дата" });
  });

  it("keeps the legacy FastAPI detail format working", async () => {
    vi.stubGlobal("fetch", respond(404, { detail: "Задача не найдена." }));
    await expect(api.getJob("x")).rejects.toThrow("Задача не найдена.");
  });

  it("formats validation errors from FastAPI", async () => {
    vi.stubGlobal("fetch", respond(422, { detail: [{ loc: ["query", "limit"], msg: "too big" }] }));
    await expect(api.getDatasets()).rejects.toThrow("limit: too big");
  });

  it("falls back to the status when the body is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => { throw new Error("html"); } }));
    await expect(api.getDatasets()).rejects.toThrow("Ошибка сервера: 502");
  });

  it("reports an unreachable server as a network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await api.getDatasets().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("NETWORK_ERROR");
  });

  it("lets aborts through untouched", async () => {
    const abort = Object.assign(new Error("aborted"), { name: "AbortError" });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
    await expect(api.getDatasets()).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("analytics client", () => {
  it("unwraps the envelope into data and metadata and sends only set params", async () => {
    const fetchMock = respond(200, { status: "success", data: { ok: 1 }, metadata: { generated_at: "t", total: 3 } });
    vi.stubGlobal("fetch", fetchMock);
    const result = await analytics.pipelineJobs({ status: "failed", search: "", offset: 0 });
    expect(result).toEqual({ data: { ok: 1 }, meta: { generated_at: "t", total: 3 } });
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/analytics\/pipeline\/jobs\?status=failed&offset=0$/);
  });

  it("encodes path segments", async () => {
    const fetchMock = respond(200, { data: {}, metadata: {} });
    vi.stubGlobal("fetch", fetchMock);
    await analytics.pipelineJob("a/b");
    expect(fetchMock.mock.calls[0][0]).toContain("/pipeline/jobs/a%2Fb");
  });
});
