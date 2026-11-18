import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, BoxplotChart, GaugeChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  BarChart, BoxplotChart, GaugeChart, HeatmapChart, LineChart, PieChart, ScatterChart,
  DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent,
  CanvasRenderer,
]);

/** Тонкая обёртка над ECharts. `option` нужно мемоизировать (useMemo) в вызывающем коде. */
export default function EChart({ option, height = 300, label }) {
  const host = useRef(null);
  const chart = useRef(null);

  useEffect(() => {
    const instance = echarts.init(host.current, null, { renderer: "canvas" });
    chart.current = instance;
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      instance.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, true);
  }, [option]);

  return <div ref={host} className="echart" style={{ height }} role="img" aria-label={label} />;
}
