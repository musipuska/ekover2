export const PALETTE = ["#22d3ee", "#2dd4bf", "#60a5fa", "#a78bfa", "#fbbf24", "#fb7185", "#34d399", "#f472b6"];
export const STATUS_COLORS = {
  passed: "#34d399", success: "#34d399", ok: "#34d399",
  warning: "#fbbf24", failed: "#fb7185", alert: "#fb7185",
  running: "#60a5fa", queued: "#94a3b8", unknown: "#94a3b8",
};

const TEXT = "#9fb3c8";
const GRID = "rgba(148, 163, 184, 0.16)";

const base = () => ({
  backgroundColor: "transparent",
  color: PALETTE,
  textStyle: { color: TEXT, fontFamily: "Inter, Arial, sans-serif", fontSize: 12 },
  tooltip: {
    backgroundColor: "rgba(8, 20, 38, 0.95)",
    borderColor: "rgba(34, 211, 238, 0.35)",
    textStyle: { color: "#e6f1ff", fontSize: 12 },
  },
  legend: { textStyle: { color: TEXT }, top: 0, type: "scroll" },
  grid: { left: 52, right: 24, top: 40, bottom: 36, containLabel: true },
});

const valueAxis = (name, extra = {}) => ({
  type: "value",
  name,
  nameTextStyle: { color: TEXT },
  axisLabel: { color: TEXT },
  splitLine: { lineStyle: { color: GRID } },
  scale: true,
  ...extra,
});

const categoryAxis = (data, extra = {}) => ({
  type: "category",
  data,
  axisLabel: { color: TEXT, hideOverlap: true },
  axisLine: { lineStyle: { color: GRID } },
  ...extra,
});

const limitLines = (lines = []) =>
  lines.length
    ? {
        silent: true,
        symbol: "none",
        lineStyle: { type: "dashed", color: "#fb7185" },
        label: { color: "#fda4af", formatter: "{b}" },
        data: lines.map((line) => ({ name: line.name, yAxis: line.value })),
      }
    : undefined;

/** Линейный график по категориям/датам. data[i] === null даёт разрыв, а не ноль. */
export function lineOption({ categories, series, yName, zoom = true, markLines = [], area = false }) {
  return {
    ...base(),
    tooltip: { ...base().tooltip, trigger: "axis" },
    xAxis: categoryAxis(categories, { boundaryGap: false }),
    yAxis: valueAxis(yName),
    dataZoom: zoom
      ? [{ type: "inside" }, { type: "slider", height: 18, bottom: 6, textStyle: { color: TEXT } }]
      : undefined,
    grid: { ...base().grid, bottom: zoom ? 60 : 36 },
    series: series.map((item, index) => ({
      name: item.name,
      type: "line",
      data: item.data,
      showSymbol: categories.length < 60,
      connectNulls: false,
      smooth: false,
      lineStyle: { width: 2 },
      itemStyle: item.color ? { color: item.color } : undefined,
      areaStyle: area ? { opacity: 0.12 } : undefined,
      markLine: index === 0 ? limitLines(markLines) : undefined,
    })),
  };
}

export function barOption({ categories, series, yName, horizontal = false, stack = false, legend = true }) {
  const cat = categoryAxis(categories, horizontal ? { inverse: true } : {});
  const val = valueAxis(yName, { scale: false });
  return {
    ...base(),
    legend: legend ? base().legend : undefined,
    tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: horizontal ? val : cat,
    yAxis: horizontal ? cat : val,
    series: series.map((item) => ({
      name: item.name,
      type: "bar",
      data: item.data,
      stack: stack ? "total" : undefined,
      itemStyle: item.color ? { color: item.color } : undefined,
      barMaxWidth: 36,
    })),
  };
}

export function donutOption({ data }) {
  return {
    ...base(),
    tooltip: { ...base().tooltip, trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { ...base().legend, top: "bottom" },
    series: [
      {
        type: "pie",
        radius: ["52%", "74%"],
        center: ["50%", "46%"],
        label: { color: TEXT, formatter: "{c}" },
        data: data.map((item) => ({
          name: item.name,
          value: item.value,
          itemStyle: { color: item.color ?? STATUS_COLORS[item.name] },
        })),
      },
    ],
  };
}

/** Гистограмма: edges.length === counts.length + 1; series — несколько наложенных рядов (stack). */
export function histogramOption({ edges, series, xName }) {
  const labels = series[0].data.map((_, i) => `${fmt(edges[i])}–${fmt(edges[i + 1])}`);
  return {
    ...barOption({ categories: labels, series, yName: "Количество", stack: series.length > 1, legend: series.length > 1 }),
    xAxis: categoryAxis(labels, { name: xName, nameLocation: "middle", nameGap: 30, nameTextStyle: { color: TEXT } }),
    grid: { ...base().grid, bottom: 52 },
  };
}

const fmt = (value) => (Math.abs(value) >= 100 ? value.toFixed(0) : Number(value.toPrecision(3)).toString());

export function scatterOption({ series, xName, yName, timeX = false }) {
  return {
    ...base(),
    tooltip: { ...base().tooltip, trigger: "item" },
    xAxis: timeX
      ? { type: "time", axisLabel: { color: TEXT }, splitLine: { show: false } }
      : valueAxis(xName, { nameLocation: "middle", nameGap: 28 }),
    yAxis: valueAxis(yName),
    dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 6, textStyle: { color: TEXT } }],
    grid: { ...base().grid, bottom: 60 },
    series: series.map((item) => ({
      name: item.name,
      type: item.line ? "line" : "scatter",
      data: item.data,
      symbolSize: item.size ?? 6,
      showSymbol: !item.line,
      lineStyle: item.line ? { width: 1.5, color: item.color } : undefined,
      itemStyle: { color: item.color, opacity: item.opacity ?? 0.85 },
      z: item.z ?? 2,
    })),
  };
}

export function heatmapOption({ labels, matrix }) {
  const data = [];
  matrix.forEach((row, y) => row.forEach((value, x) => {
    if (value !== null && value !== undefined) data.push([x, y, Number(value.toFixed(3))]);
  }));
  return {
    ...base(),
    tooltip: { ...base().tooltip, position: "top", formatter: (p) => `${labels[p.value[1]]} × ${labels[p.value[0]]}: ${p.value[2]}` },
    grid: { left: 24, right: 24, top: 16, bottom: 70, containLabel: true },
    xAxis: { type: "category", data: labels, axisLabel: { color: TEXT, rotate: 30 }, splitArea: { show: true } },
    yAxis: { type: "category", data: labels, inverse: true, axisLabel: { color: TEXT }, splitArea: { show: true } },
    visualMap: {
      min: -1, max: 1, orient: "horizontal", left: "center", bottom: 0, calculable: false,
      textStyle: { color: TEXT }, inRange: { color: ["#fb7185", "#1e293b", "#22d3ee"] },
    },
    series: [{
      type: "heatmap", data,
      label: { show: labels.length <= 10, color: "#e6f1ff", fontSize: 11 },
      emphasis: { itemStyle: { borderColor: "#fff", borderWidth: 1 } },
    }],
  };
}

export function boxplotOption({ box, name, unit }) {
  return {
    ...base(),
    legend: undefined,
    tooltip: { ...base().tooltip, trigger: "item" },
    grid: { left: 52, right: 24, top: 24, bottom: 24, containLabel: true },
    xAxis: categoryAxis([name]),
    yAxis: valueAxis(unit),
    series: [
      {
        name, type: "boxplot",
        data: [[box.low, box.q1, box.median, box.q3, box.high]],
        itemStyle: { color: "rgba(34, 211, 238, 0.18)", borderColor: "#22d3ee" },
      },
      {
        name: "Выбросы", type: "scatter",
        data: (box.outliers ?? []).map((value) => [0, value]),
        itemStyle: { color: "#fb7185" }, symbolSize: 6,
      },
    ],
  };
}

export function gaugeOption({ value, min = 0, max = 1, name }) {
  return {
    ...base(),
    series: [{
      type: "gauge", min, max, startAngle: 210, endAngle: -30, radius: "92%",
      progress: { show: true, width: 14 },
      axisLine: { lineStyle: { width: 14, color: [[1, "rgba(148,163,184,0.18)"]] } },
      axisTick: { show: false }, splitLine: { show: false },
      axisLabel: { color: TEXT, distance: 18 },
      pointer: { show: false },
      anchor: { show: false },
      title: { color: TEXT, offsetCenter: [0, "62%"] },
      detail: { valueAnimation: true, color: "#e6f1ff", fontSize: 28, offsetCenter: [0, "18%"], formatter: (v) => v.toFixed(2) },
      itemStyle: { color: value >= 0.9 * max ? "#34d399" : value >= 0.6 * max ? "#fbbf24" : "#fb7185" },
      data: [{ value, name }],
    }],
  };
}
