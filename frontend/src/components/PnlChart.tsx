import { useEffect, useRef } from "react";
import { createChart, UTCTimestamp } from "lightweight-charts";
import type { JournalSummary } from "../api/journal";
import { toChartTime } from "../chartTime";
import { CHART_COLORS } from "./CandleChart";

type PnlPoint = JournalSummary["pnl_points"][number];

const PNL_CHART_HEIGHT = 240;
const LINE_COLOR = "#e4ecf2";
// The per-result bars sit in the bottom part, under the running total.
const BAR_MARGINS = { top: 0.6, bottom: 0 };

interface MergedPoint {
  time: UTCTimestamp;
  pnl: number;
  cumulative: number;
}

// lightweight-charts throws on repeated times; two exits in the same second become one point.
function mergeByTime(points: PnlPoint[]): MergedPoint[] {
  const merged = new Map<number, MergedPoint>();
  for (const point of points) {
    const time = toChartTime(point.time) as UTCTimestamp;
    const existing = merged.get(time);
    merged.set(time, { time, pnl: (existing?.pnl ?? 0) + point.pnl, cumulative: point.cumulative });
  }
  return [...merged.values()].sort((left, right) => left.time - right.time);
}

export function PnlChart({ points }: { points: PnlPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: PNL_CHART_HEIGHT,
      layout: { background: { color: CHART_COLORS.background }, textColor: CHART_COLORS.text },
      grid: { vertLines: { color: CHART_COLORS.grid }, horzLines: { color: CHART_COLORS.grid } },
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const merged = mergeByTime(points);
    const bars = chart.addHistogramSeries({ priceScaleId: "results", lastValueVisible: false, priceLineVisible: false });
    bars.priceScale().applyOptions({ scaleMargins: BAR_MARGINS });
    bars.setData(
      merged.map((point) => ({
        time: point.time,
        value: point.pnl,
        color: point.pnl >= 0 ? CHART_COLORS.volumeUp : CHART_COLORS.volumeDown,
      })),
    );
    const line = chart.addLineSeries({ color: LINE_COLOR, lineWidth: 2, title: "Net P&L" });
    line.setData(merged.map((point) => ({ time: point.time, value: point.cumulative })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [points]);

  return <div ref={containerRef} className="pnl-chart" />;
}
