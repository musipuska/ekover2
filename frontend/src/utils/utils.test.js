import { describe, expect, it } from "vitest";

import { formatDuration, formatInt, formatKpi, formatNumber, formatPercent, NA } from "./format";
import { aggregateTrends, bucketKey } from "./series";

describe("format", () => {
  it("missing values are N/A, never zero", () => {
    expect(formatInt(null)).toBe(NA);
    expect(formatNumber(undefined)).toBe(NA);
    expect(formatNumber(NaN)).toBe(NA);
    expect(formatPercent(null)).toBe(NA);
    expect(formatDuration(null)).toBe(NA);
    expect(formatKpi(null, "datasets")).toBe(NA);
  });

  it("a real zero stays zero", () => {
    expect(formatInt(0)).toBe("0");
    expect(formatPercent(0)).toBe("0%");
    expect(formatKpi(0, "jobs_failed")).toBe("0");
  });

  it("formats ratios as percent and durations in readable units", () => {
    expect(formatPercent(0.1234, 1)).toBe("12,3%");
    expect(formatDuration(0.25)).toBe("250 мс");
    expect(formatDuration(12.34)).toBe("12,3 с");
    expect(formatDuration(125)).toBe("2 мин 5 с");
  });
});

describe("series", () => {
  it("buckets days into weeks starting on Monday and months", () => {
    expect(bucketKey("2026-01-07", "week")).toBe("2026-01-05"); // среда → понедельник
    expect(bucketKey("2026-01-04", "week")).toBe("2025-12-29"); // воскресенье → предыдущий понедельник
    expect(bucketKey("2026-03-19", "month")).toBe("2026-03-01");
    expect(bucketKey("2026-03-19", "day")).toBe("2026-03-19");
  });

  const rows = [
    { date: "2026-01-05", station_id: "a", measurement_count: 1, avg_value: 10, min_value: 10, max_value: 10 },
    { date: "2026-01-06", station_id: "a", measurement_count: 3, avg_value: 20, min_value: 15, max_value: 25 },
    { date: "2026-01-06", station_id: "b", measurement_count: 4, avg_value: 5, min_value: 1, max_value: 9 },
    { date: "2026-01-13", station_id: "a", measurement_count: 2, avg_value: 30, min_value: 30, max_value: 30 },
  ];

  it("weights the mean by measurement count and keeps exact min/max", () => {
    const week = aggregateTrends(rows, "week").a;
    expect(week).toHaveLength(2);
    expect(week[0]).toMatchObject({ key: "2026-01-05", count: 4, min: 10, max: 25 });
    expect(week[0].avg).toBeCloseTo((10 * 1 + 20 * 3) / 4);
  });

  it("builds an all-stations series and per-station series", () => {
    const grouped = aggregateTrends(rows, "day");
    expect(Object.keys(grouped).sort()).toEqual(["__all__", "a", "b"]);
    const day = grouped.__all__.find((p) => p.key === "2026-01-06");
    expect(day.count).toBe(7);
    expect(day.avg).toBeCloseTo((20 * 3 + 5 * 4) / 7);
  });

  it("returns nothing for no rows", () => {
    expect(aggregateTrends([], "day")).toEqual({});
  });
});
