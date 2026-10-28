import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  HistogramData,
  IChartApi,
  IPriceLine,
  ISeriesApi,
  LineStyle,
  MouseEventParams,
  UTCTimestamp,
  WhitespaceData,
} from "lightweight-charts";
import type { Bar } from "../api/bars";
import { describeBar } from "../barLegend";
import { barSession, BarSession, toChartTime } from "../chartTime";

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
  // How many of the most recent bars to show at first; the user can scroll back.
  visibleBars?: number;
  // Shade pre-market and after-hours bars (intraday charts only).
  shadeSessions?: boolean;
  // Daily bars are labelled by date in the hover legend, intraday bars by time.
  isDaily?: boolean;
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
  volumeUp: "rgba(70, 192, 138, 0.45)",
  volumeDown: "rgba(229, 107, 93, 0.45)",
  preMarket: "rgba(64, 190, 200, 0.2)",
  afterHours: "rgba(180, 120, 240, 0.2)",
} as const;

const SESSION_SHADES: Record<BarSession, string | null> = {
  "pre-market": CHART_COLORS.preMarket,
  regular: null,
  "after-hours": CHART_COLORS.afterHours,
};
// Volume uses the bottom fifth of the chart; candles keep clear of it.
const VOLUME_MARGINS = { top: 0.8, bottom: 0 };
const CANDLE_MARGINS = { top: 0.08, bottom: 0.25 };
// Shading is a full-height bar of value 1 on its own hidden scale.
const SHADE_HEIGHT = 1;
const FULL_HEIGHT_MARGINS = { top: 0, bottom: 0 };

const CHART_HEIGHT = 420;
// Empty space after the last bar so the latest candle isn't against the axis.
const RIGHT_PADDING_BARS = 4;

function toTime(isoTime: string): UTCTimestamp {
  return toChartTime(isoTime) as UTCTimestamp;
}

function toVolumePoints(bars: Bar[]): HistogramData[] {
  return bars.map((bar) => ({
    time: toTime(bar.time),
    value: bar.volume,
    color: bar.close >= bar.open ? CHART_COLORS.volumeUp : CHART_COLORS.volumeDown,
  }));
}

// lightweight-charts has no background bands, so session shading is a histogram
// behind the candles; regular-hours bars get an empty point (nothing drawn).
function toSessionShading(bars: Bar[]): (HistogramData | WhitespaceData)[] {
  return bars.map((bar) => {
    const time = toTime(bar.time);
    const shade = SESSION_SHADES[barSession(bar.time)];
    return shade ? { time, value: SHADE_HEIGHT, color: shade } : { time };
  });
}

// lightweight-charts throws on unsorted or repeated times.
function toSortedUniquePoints(points: [string, number][]): { time: UTCTimestamp; value: number }[] {
  const byTime = new Map(points.map(([time, price]) => [toTime(time), price]));
  return [...byTime.entries()].sort(([left], [right]) => left - right).map(([time, value]) => ({ time, value }));
}

function BarLegend({ bar, isDaily }: { bar: Bar; isDaily: boolean }) {
  const text = describeBar(bar, isDaily);
  const valueClass = text.direction === "up" ? "gain" : "loss";
  return (
    <div className="bar-legend" data-testid="bar-legend">
      <span className="muted">{text.time}</span>
      {(["open", "high", "low", "close"] as const).map((field) => (
        <span key={field}>
          <span className="muted bar-legend-label">{field[0].toUpperCase()}</span>
          <span className={valueClass}>{text[field]}</span>
        </span>
      ))}
      <span className={valueClass}>{text.change}</span>
      <span>
        <span className="muted">Vol </span>
        {text.volume}
      </span>
    </div>
  );
}

export function CandleChart({
  bars,
  levels,
  outline,
  vwap,
  visibleBars,
  shadeSessions = false,
  isDaily = false,
}: CandleChartProps) {
  // Chart time of the bar under the mouse; null when the mouse is off the chart.
  const [hoveredTime, setHoveredTime] = useState<number | null>(null);
  const barsByTime = useMemo(() => new Map(bars.map((bar) => [toTime(bar.time) as number, bar])), [bars]);
  // Off the chart, or on a time with no bar (e.g. right of the last one), show the latest bar.
  const legendBar = (hoveredTime != null ? barsByTime.get(hoveredTime) : undefined) ?? bars[bars.length - 1];
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const sessionsRef = useRef<ISeriesApi<"Histogram"> | null>(null);

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
    // Added first so it's drawn behind everything else.
    const sessions = chart.addHistogramSeries({
      priceScaleId: "sessions",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    sessions.priceScale().applyOptions({ scaleMargins: FULL_HEIGHT_MARGINS });
    sessionsRef.current = sessions;
    const candles = chart.addCandlestickSeries({
      upColor: CHART_COLORS.up,
      downColor: CHART_COLORS.down,
      wickUpColor: CHART_COLORS.up,
      wickDownColor: CHART_COLORS.down,
      borderVisible: false,
    });
    candles.priceScale().applyOptions({ scaleMargins: CANDLE_MARGINS });
    candlesRef.current = candles;
    const volume = chart.addHistogramSeries({
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      lastValueVisible: false,
      priceLineVisible: false,
    });
    volume.priceScale().applyOptions({ scaleMargins: VOLUME_MARGINS });
    volumeRef.current = volume;
    // The crosshair snaps to a bar's time anywhere on the chart, so this works
    // over candles, volume or empty space alike.
    const handleCrosshairMove = (param: MouseEventParams) => {
      setHoveredTime(typeof param.time === "number" ? param.time : null);
    };
    chart.subscribeCrosshairMove(handleCrosshairMove);
    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.remove();
      chartRef.current = null;
      candlesRef.current = null;
      volumeRef.current = null;
      sessionsRef.current = null;
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
    volumeRef.current?.setData(toVolumePoints(bars));
    sessionsRef.current?.setData(shadeSessions ? toSessionShading(bars) : []);

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
    if (visibleBars != null && bars.length > visibleBars) {
      chart.timeScale().setVisibleLogicalRange({
        from: bars.length - visibleBars,
        to: bars.length - 1 + RIGHT_PADDING_BARS,
      });
    } else {
      chart.timeScale().fitContent();
    }

    return () => {
      // On unmount the chart-creating effect's cleanup runs first and removes
      // the chart; touching its series afterwards throws inside the library.
      if (chartRef.current !== chart) {
        return;
      }
      priceLines.forEach((line) => candles.removePriceLine(line));
      extraSeries.forEach((series) => chart.removeSeries(series));
    };
  }, [bars, levels, outline, vwap, visibleBars, shadeSessions]);

  return (
    <div className="candle-chart-frame">
      <div ref={containerRef} className="candle-chart" />
      {legendBar && <BarLegend bar={legendBar} isDaily={isDaily} />}
    </div>
  );
}
