import { cleanup, render } from "@testing-library/react";
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
    removePriceLine: vi.fn(throwIfRemoved),
  };
  const lineSeries = { setData: vi.fn() };
  const timeScale = { fitContent: vi.fn(), setVisibleLogicalRange: vi.fn() };
  const instance = {
    addCandlestickSeries: vi.fn(() => candleSeries),
    addLineSeries: vi.fn(() => lineSeries),
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
  return { instance, candleSeries, lineSeries, timeScale, createChart };
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

  it("draws VWAP and the pattern outline as lines", () => {
    render(
      <CandleChart bars={BARS} levels={[]} outline={[["2026-10-20T09:30:00-04:00", 2.0]]} vwap={[2.02, null]} />,
    );

    expect(chart.instance.addLineSeries).toHaveBeenCalledTimes(2);
    expect(chart.lineSeries.setData).toHaveBeenCalledWith([expect.objectContaining({ value: 2.02 })]);
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
