import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PnlChart } from "./PnlChart";

const chart = vi.hoisted(() => {
  const line = { setData: vi.fn() };
  const histogram = { setData: vi.fn(), priceScale: vi.fn(() => ({ applyOptions: vi.fn() })) };
  const instance = {
    addLineSeries: vi.fn(() => line),
    addHistogramSeries: vi.fn(() => histogram),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
    remove: vi.fn(),
  };
  return { instance, line, histogram, createChart: vi.fn(() => instance) };
});
vi.mock("lightweight-charts", () => ({ createChart: chart.createChart }));

describe("PnlChart", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("draws the running total as a line and each result as a coloured bar", () => {
    render(
      <PnlChart
        points={[
          { time: "2026-11-09T09:50:00-05:00", pnl: 50, cumulative: 50 },
          { time: "2026-11-09T10:05:00-05:00", pnl: -20, cumulative: 30 },
        ]}
      />,
    );

    expect(chart.line.setData.mock.calls[0][0].map((point: { value: number }) => point.value)).toEqual([50, 30]);
    const bars = chart.histogram.setData.mock.calls[0][0];
    expect(bars.map((bar: { value: number }) => bar.value)).toEqual([50, -20]);
    expect(bars[0].color).not.toEqual(bars[1].color);
  });

  it("merges results booked in the same second, which the chart can't draw twice", () => {
    render(
      <PnlChart
        points={[
          { time: "2026-11-09T09:50:00-05:00", pnl: 50, cumulative: 50 },
          { time: "2026-11-09T09:50:00-05:00", pnl: 10, cumulative: 60 },
        ]}
      />,
    );

    expect(chart.line.setData.mock.calls[0][0]).toHaveLength(1);
    expect(chart.line.setData.mock.calls[0][0][0].value).toBe(60);
    expect(chart.histogram.setData.mock.calls[0][0][0].value).toBe(60);
  });
});
