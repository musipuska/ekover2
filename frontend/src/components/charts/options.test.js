import { describe, expect, it } from "vitest";

import { boxplotOption, donutOption, heatmapOption, histogramOption, lineOption } from "./options";

describe("chart options", () => {
  it("line keeps null values as gaps and draws limit lines only when provided", () => {
    const option = lineOption({ categories: ["a", "b", "c"], series: [{ name: "x", data: [1, null, 3] }], yName: "u" });
    expect(option.series[0].data).toEqual([1, null, 3]);
    expect(option.series[0].connectNulls).toBe(false);
    expect(option.series[0].markLine).toBeUndefined();

    const limited = lineOption({ categories: ["a"], series: [{ name: "x", data: [1] }], yName: "u", markLines: [{ name: "max", value: 14 }] });
    expect(limited.series[0].markLine.data).toEqual([{ name: "max", yAxis: 14 }]);
  });

  it("heatmap skips cells without a value instead of drawing zero", () => {
    const option = heatmapOption({ labels: ["a", "b"], matrix: [[1, null], [null, 1]] });
    expect(option.series[0].data).toEqual([[0, 0, 1], [1, 1, 1]]);
  });

  it("histogram builds one label per bin from edges", () => {
    const option = histogramOption({ edges: [0, 1, 2], series: [{ name: "n", data: [3, 4] }], xName: "ph" });
    expect(option.xAxis.data).toEqual(["0–1", "1–2"]);
  });

  it("donut maps status names to semantic colours", () => {
    const option = donutOption({ data: [{ name: "failed", value: 2 }, { name: "passed", value: 5 }] });
    expect(option.series[0].data.map((d) => d.itemStyle.color)).toEqual(["#fb7185", "#34d399"]);
  });

  it("boxplot passes through computed whiskers and outliers", () => {
    const option = boxplotOption({ box: { low: 1, q1: 2, median: 3, q3: 4, high: 5, outliers: [9] }, name: "ph", unit: "ph" });
    expect(option.series[0].data).toEqual([[1, 2, 3, 4, 5]]);
    expect(option.series[1].data).toEqual([[0, 9]]);
  });
});
