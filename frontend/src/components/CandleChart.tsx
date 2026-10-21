import { useEffect, useRef } from "react";
import {
  createChart,
  IChartApi,
  IPriceLine,
  ISeriesApi,
  LineStyle,
  UTCTimestamp,
} from "lightweight-charts";
import type { Bar } from "../api/bars";
import { toChartTime } from "../chartTime";

export type ChartLevelKind = "level" | "session" | "entry" | "stop" | "target";

export interface ChartLevel {
  price: number;
  label: string;
  kind: ChartLevelKind;
}

interface CandleChartProps {
  bars: Bar[];
  levels: ChartLevel[];
  outline: [string, number][] | null;
  vwap: (number | null)[] | null;
}

// Mirrors the tokens in styles.css; the chart draws on canvas and can't read CSS variables.
export const CHART_COLORS = {
  background: "#1b2a37",
  grid: "#223444",
  text: "#8ea2b2",
  up: "#46c08a",
  down: "#e56b5d",
  entry: "#f0b44c",
  stop: "#e56b5d",
  target: "#46c08a",
  level: "#5d7487",
  session: "#7b6aa6",
  vwap: "#c9a8ff",
  outline: "#f0b44c",
} as const;

const CHART_HEIGHT = 420;

function toTime(isoTime: string): UTCTimestamp {
  return toChartTime(isoTime) as UTCTimestamp;
}

// lightweight-charts throws on unsorted or repeated times.
function toSortedUniquePoints(points: [string, number][]): { time: UTCTimestamp; value: number }[] {
  const byTime = new Map(points.map(([time, price]) => [toTime(time), price]));
  return [...byTime.entries()].sort(([left], [right]) => left - right).map(([time, value]) => ({ time, value }));
}

export function CandleChart({ bars, levels, outline, vwap }: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: CHART_HEIGHT,
      layout: { background: { color: CHART_COLORS.background }, textColor: CHART_COLORS.text },
      grid: { vertLines: { color: CHART_COLORS.grid }, horzLines: { color: CHART_COLORS.grid } },
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    chartRef.current = chart;
    candlesRef.current = chart.addCandlestickSeries({
      upColor: CHART_COLORS.up,
      downColor: CHART_COLORS.down,
      wickUpColor: CHART_COLORS.up,
      wickDownColor: CHART_COLORS.down,
      borderVisible: false,
    });
    return () => {
      chart.remove();
      chartRef.current = null;
      candlesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    const candles = candlesRef.current;
    if (!chart || !candles) {
      return;
    }
    candles.setData(
      bars.map((bar) => ({ time: toTime(bar.time), open: bar.open, high: bar.high, low: bar.low, close: bar.close })),
    );

    const priceLines: IPriceLine[] = levels.map((level) =>
      candles.createPriceLine({
        price: level.price,
        color: CHART_COLORS[level.kind],
        lineWidth: level.kind === "level" || level.kind === "session" ? 1 : 2,
        lineStyle: level.kind === "level" || level.kind === "session" ? LineStyle.Dashed : 0,
        axisLabelVisible: true,
        title: level.label,
      }),
    );

    const extraSeries: ISeriesApi<"Line">[] = [];
    if (vwap) {
      const vwapSeries = chart.addLineSeries({ color: CHART_COLORS.vwap, lineWidth: 1, title: "VWAP" });
      vwapSeries.setData(
        bars.flatMap((bar, index) => (vwap[index] == null ? [] : [{ time: toTime(bar.time), value: vwap[index] as number }])),
      );
      extraSeries.push(vwapSeries);
    }
    if (outline && outline.length > 0) {
      const outlineSeries = chart.addLineSeries({ color: CHART_COLORS.outline, lineWidth: 2, lineStyle: LineStyle.Dotted });
      outlineSeries.setData(toSortedUniquePoints(outline));
      extraSeries.push(outlineSeries);
    }
    chart.timeScale().fitContent();

    return () => {
      priceLines.forEach((line) => candles.removePriceLine(line));
      extraSeries.forEach((series) => chart.removeSeries(series));
    };
  }, [bars, levels, outline, vwap]);

  return <div ref={containerRef} className="candle-chart" />;
}
