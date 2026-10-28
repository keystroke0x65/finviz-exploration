import { act, cleanup, render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CandleChart, CHART_COLORS } from "./CandleChart";

const chart = vi.hoisted(() => {
  const state = { isRemoved: false };
  // Like the real library: touching a removed chart throws.
  const throwIfRemoved = () => {
    if (state.isRemoved) throw new Error("Value is undefined");
  };
  const candleSeries = {
    setData: vi.fn(),
    createPriceLine: vi.fn((options) => options),
    priceScale: vi.fn(() => priceScale),
    removePriceLine: vi.fn(throwIfRemoved),
  };
  const lineSeries = { setData: vi.fn() };
  const priceScale = { applyOptions: vi.fn() };
  const volumeSeries = { setData: vi.fn(), priceScale: vi.fn(() => priceScale) };
  const sessionSeries = { setData: vi.fn(), priceScale: vi.fn(() => priceScale) };
  const histogramSeries = [sessionSeries, volumeSeries];
  const timeScale = { fitContent: vi.fn(), setVisibleLogicalRange: vi.fn() };
  const crosshairHandlers: ((param: { time?: number }) => void)[] = [];
  const instance = {
    subscribeCrosshairMove: vi.fn((handler: (param: { time?: number }) => void) => crosshairHandlers.push(handler)),
    unsubscribeCrosshairMove: vi.fn(),
    addCandlestickSeries: vi.fn(() => candleSeries),
    addLineSeries: vi.fn(() => lineSeries),
    // The chart adds the session shading first (so it sits behind the candles), then volume.
    addHistogramSeries: vi.fn(() => histogramSeries[(instance.addHistogramSeries.mock.calls.length - 1) % 2]),
    removeSeries: vi.fn(throwIfRemoved),
    timeScale: vi.fn(() => timeScale),
    remove: vi.fn(() => {
      state.isRemoved = true;
    }),
  };
  const createChart = vi.fn(() => {
    state.isRemoved = false;
    return instance;
  });
  // Simulates the mouse moving over the bar at a chart time (undefined: off the chart).
  const moveCrosshair = (time?: number) => crosshairHandlers.forEach((handler) => handler({ time }));
  return { instance, candleSeries, lineSeries, volumeSeries, sessionSeries, timeScale, createChart, moveCrosshair };
});
vi.mock("lightweight-charts", () => ({ createChart: chart.createChart, LineStyle: { Dashed: 2, Dotted: 1 } }));

const BARS = [
  { time: "2026-10-20T09:30:00-04:00", open: 2, high: 2.1, low: 1.95, close: 2.05, volume: 1000 },
  { time: "2026-10-20T09:31:00-04:00", open: 2.05, high: 2.2, low: 2.0, close: 2.15, volume: 1500 },
];

describe("CandleChart", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("draws candles and a price line for each level with its colour", () => {
    render(
      <CandleChart
        bars={BARS}
        levels={[
          { price: 2.0, label: "Entry", kind: "entry" },
          { price: 1.9, label: "Stop", kind: "stop" },
          { price: 2.3, label: "Target", kind: "target" },
          { price: 2.5, label: "Daily level", kind: "level" },
        ]}
        outline={null}
        vwap={null}
      />,
    );

    expect(chart.candleSeries.setData).toHaveBeenCalledWith([
      expect.objectContaining({ open: 2, high: 2.1, low: 1.95, close: 2.05 }),
      expect.objectContaining({ close: 2.15 }),
    ]);
    const lines = chart.candleSeries.createPriceLine.mock.calls.map(([options]) => [options.price, options.color]);
    expect(lines).toEqual([
      [2.0, CHART_COLORS.entry],
      [1.9, CHART_COLORS.stop],
      [2.3, CHART_COLORS.target],
      [2.5, CHART_COLORS.level],
    ]);
  });

  it("draws a volume bar under each candle, coloured by direction", () => {
    const falling = { ...BARS[1], time: "2026-10-20T09:32:00-04:00", open: 2.15, close: 2.1, volume: 700 };
    render(<CandleChart bars={[...BARS, falling]} levels={[]} outline={null} vwap={null} />);

    const volumes = chart.volumeSeries.setData.mock.calls[0][0].map((point: { value: number; color: string }) => [
      point.value,
      point.color,
    ]);
    expect(volumes).toEqual([
      [1000, CHART_COLORS.volumeUp],
      [1500, CHART_COLORS.volumeUp],
      [700, CHART_COLORS.volumeDown],
    ]);
  });

  it("shades pre-market and after-hours bars when asked", () => {
    const sessionBars = [
      { ...BARS[0], time: "2026-10-20T08:00:00-04:00" },
      { ...BARS[0], time: "2026-10-20T10:00:00-04:00" },
      { ...BARS[0], time: "2026-10-20T17:00:00-04:00" },
    ];
    render(<CandleChart bars={sessionBars} levels={[]} outline={null} vwap={null} shadeSessions />);

    const shading = chart.sessionSeries.setData.mock.calls[0][0];
    expect(shading).toHaveLength(3);
    expect(shading[0]).toMatchObject({ value: 1, color: CHART_COLORS.preMarket });
    expect(shading[1]).not.toHaveProperty("value"); // regular hours: nothing drawn
    expect(shading[2]).toMatchObject({ value: 1, color: CHART_COLORS.afterHours });
  });

  it("shades nothing on charts without sessions", () => {
    render(<CandleChart bars={BARS} levels={[]} outline={null} vwap={null} />);

    expect(chart.sessionSeries.setData).toHaveBeenCalledWith([]);
  });

  it("draws VWAP and the pattern outline as lines", () => {
    render(
      <CandleChart bars={BARS} levels={[]} outline={[["2026-10-20T09:30:00-04:00", 2.0]]} vwap={[2.02, null]} />,
    );

    expect(chart.instance.addLineSeries).toHaveBeenCalledTimes(2);
    expect(chart.lineSeries.setData).toHaveBeenCalledWith([expect.objectContaining({ value: 2.02 })]);
  });

  it("shows the latest bar's OHLCV when the mouse isn't over the chart", () => {
    render(<CandleChart bars={BARS} levels={[]} outline={null} vwap={null} />);

    const legend = screen.getByTestId("bar-legend");
    expect(legend).toHaveTextContent("Oct 20, 9:31 AM");
    expect(legend).toHaveTextContent("O2.05H2.20L2.00C2.15");
    expect(legend).toHaveTextContent("Vol 1.5K");
  });

  it("shows the hovered bar's OHLCV and returns to the latest when the mouse leaves", () => {
    render(<CandleChart bars={BARS} levels={[]} outline={null} vwap={null} />);
    const firstBarTime = chart.candleSeries.setData.mock.calls[0][0][0].time;

    act(() => chart.moveCrosshair(firstBarTime));
    expect(screen.getByTestId("bar-legend")).toHaveTextContent("Oct 20, 9:30 AM");
    expect(screen.getByTestId("bar-legend")).toHaveTextContent("O2.00H2.10L1.95C2.05");

    act(() => chart.moveCrosshair(undefined));
    expect(screen.getByTestId("bar-legend")).toHaveTextContent("Oct 20, 9:31 AM");
  });

  it("labels daily bars by date", () => {
    render(
      <CandleChart bars={[{ ...BARS[0], time: "2026-10-20T00:00:00-04:00" }]} levels={[]} outline={null} vwap={null} isDaily />,
    );

    expect(screen.getByTestId("bar-legend")).toHaveTextContent("Oct 20, 2026");
  });

  it("stops listening to the mouse when removed", () => {
    const { unmount } = render(<CandleChart bars={BARS} levels={[]} outline={null} vwap={null} />);

    unmount();

    expect(chart.instance.unsubscribeCrosshairMove).toHaveBeenCalled();
  });

  it("removes the chart on unmount", () => {
    const { unmount } = render(<CandleChart bars={BARS} levels={[]} outline={null} vwap={null} />);

    unmount();

    expect(chart.instance.remove).toHaveBeenCalled();
  });

  it("survives React StrictMode's mount-unmount-mount in development", () => {
    const strictRender = () =>
      render(
        <StrictMode>
          <CandleChart bars={BARS} levels={[{ price: 2.0, label: "Entry", kind: "entry" }]} outline={null} vwap={[2.0, 2.1]} />
        </StrictMode>,
      );

    expect(strictRender).not.toThrow();
    expect(chart.createChart).toHaveBeenCalledTimes(2);
  });

  it("opens zoomed to the most recent bars when there are more than it shows", () => {
    const manyBars = Array.from({ length: 500 }, (_, index) => ({
      ...BARS[0],
      time: new Date(Date.UTC(2026, 9, 1) + index * 300_000).toISOString(),
    }));

    render(<CandleChart bars={manyBars} levels={[]} outline={null} vwap={null} visibleBars={192} />);

    expect(chart.timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({ from: 308, to: 503 });
    expect(chart.timeScale.fitContent).not.toHaveBeenCalled();
  });

  it("fits everything when there are fewer bars than it shows", () => {
    render(<CandleChart bars={BARS} levels={[]} outline={null} vwap={null} visibleBars={192} />);

    expect(chart.timeScale.fitContent).toHaveBeenCalled();
  });
});
