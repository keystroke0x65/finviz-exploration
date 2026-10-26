import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Setup } from "../api/setups";
import { StockView } from "./StockView";

const api = vi.hoisted(() => ({
  fetchBars: vi.fn(),
  fetchStockSetups: vi.fn(),
  fetchStockVerdict: vi.fn(),
  runScan: vi.fn(),
  fetchQuote: vi.fn(),
  chartProps: [] as { levels: { price: number; kind: string }[]; shadeSessions?: boolean }[],
}));
vi.mock("../api/bars", () => ({ fetchBars: (...args: unknown[]) => api.fetchBars(...args) }));
vi.mock("../api/setups", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/setups")>()),
  fetchStockSetups: (ticker: string) => api.fetchStockSetups(ticker),
  fetchStockVerdict: (ticker: string) => api.fetchStockVerdict(ticker),
  runScan: (ticker?: string) => api.runScan(ticker),
}));
vi.mock("../api/stocks", () => ({ fetchQuote: (ticker: string) => api.fetchQuote(ticker) }));
vi.mock("./CandleChart", () => ({
  CandleChart: (props: { levels: { price: number; kind: string }[]; shadeSessions?: boolean }) => {
    api.chartProps.push(props);
    return <div data-testid="chart" />;
  },
}));

const SETUP: Setup = {
  id: 7, ticker: "HOST", pattern: "bull_flag", direction: "long", timeframe: "5m", entry: 2.12, stop: 2.05,
  capped_target: 2.33, target_3r: 2.33, available_reward_risk: 3, risk_percent: 3.3, blocking_level: null,
  partial_1r: 2.19, partial_2r: 2.26, trailing_stop: null, quality: 0.7, score: 80, score_parts: {},
  key_points: [["2026-10-20T13:30:00Z", 2.0]], state: "forming", triggered_at: null, session: "regular",
  detected_at: "2026-10-20T13:35:00Z", last_seen_at: "2026-10-20T13:35:30Z", has_conflict: false,
};

const BARS_RESPONSE = {
  bars: [{ time: "2026-10-20T09:30:00-04:00", open: 2, high: 2.1, low: 1.95, close: 2.05, volume: 1000 }],
  fetched_at: "2026-10-20T13:36:00Z",
  daily_levels: [{ price: 2.5, touches: 3 }],
  session: null,
  vwap: [2.01],
};

describe("StockView", () => {
  beforeEach(() => {
    api.fetchBars.mockResolvedValue(BARS_RESPONSE);
    api.fetchStockSetups.mockResolvedValue({ setups: [SETUP], warnings: [], show_short_setups: false });
    api.fetchQuote.mockResolvedValue({ Ticker: "HOST", Company: "Host Digital Inc" });
    api.fetchStockVerdict.mockResolvedValue(null);
    api.chartProps = [];
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("asks for a ticker when none is chosen", () => {
    render(<StockView ticker={null} onTickerChange={vi.fn()} />);

    expect(screen.getByLabelText("Stock ticker")).toBeInTheDocument();
    expect(api.fetchBars).not.toHaveBeenCalled();
  });

  it("loads 5m bars by default and switches timeframe", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    await screen.findByTestId("chart");
    expect(api.fetchBars).toHaveBeenCalledWith("HOST", "5m");
    fireEvent.click(screen.getByRole("button", { name: "1m" }));

    await vi.waitFor(() => expect(api.fetchBars).toHaveBeenCalledWith("HOST", "1m"));
  });

  it("draws the selected setup's entry, stop and target", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: /Bull flag/ }));

    await vi.waitFor(() => {
      const levels = api.chartProps[api.chartProps.length - 1].levels;
      expect(levels).toEqual(expect.arrayContaining([
        expect.objectContaining({ price: 2.12, kind: "entry" }),
        expect.objectContaining({ price: 2.05, kind: "stop" }),
        expect.objectContaining({ price: 2.33, kind: "target" }),
        expect.objectContaining({ price: 2.5, kind: "level" }),
      ]));
    });
  });

  it("shades and labels the sessions on intraday charts only", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    expect(await screen.findByText("Pre-market")).toBeInTheDocument();
    expect(screen.getByText("After-hours")).toBeInTheDocument();
    expect(api.chartProps[api.chartProps.length - 1].shadeSessions).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "daily" }));

    await vi.waitFor(() => expect(api.chartProps[api.chartProps.length - 1].shadeSessions).toBe(false));
    expect(screen.queryByText("Pre-market")).not.toBeInTheDocument();
  });

  it("says when each setup triggered", async () => {
    api.fetchStockSetups.mockResolvedValue({
      setups: [{ ...SETUP, state: "triggered", triggered_at: "2026-10-20T13:42:00Z" }], warnings: [],
      show_short_setups: false,
    });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    expect(await screen.findByText(/Triggered 9:42 AM/)).toBeInTheDocument();
  });

  it("scans the stock and reloads its setups", async () => {
    api.runScan.mockResolvedValue({ scanned: ["HOST"], failed: [], setups_found: 1, scanned_at: "x" });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Scan this stock" }));

    await vi.waitFor(() => expect(api.fetchStockSetups).toHaveBeenCalledTimes(2));
    expect(api.runScan).toHaveBeenCalledWith("HOST");
  });

  it("links to Finviz and shows the quote", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    expect(await screen.findByText("Host Digital Inc")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open HOST on Finviz" })).toHaveAttribute(
      "href", "https://finviz.com/quote.ashx?t=HOST",
    );
  });

  it("draws only the breakdown level for a bearish warning", async () => {
    const warning = {
      id: 8, ticker: "HOST", pattern: "low_of_day_break", direction: "short" as const, timeframe: "5m" as const,
      entry: 1.9, state: "forming" as const, triggered_at: null, key_points: [], detected_at: "2026-10-20T13:35:00Z",
      last_seen_at: "2026-10-20T13:35:30Z",
    };
    api.fetchStockSetups.mockResolvedValue({ setups: [], warnings: [warning], show_short_setups: false });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: /Low-of-day break/ }));

    await vi.waitFor(() => {
      const kinds = api.chartProps[api.chartProps.length - 1].levels.map((level) => level.kind);
      expect(kinds).not.toContain("stop");
      expect(kinds).not.toContain("target");
    });
  });

  it("shows the verdict and its reasons on the stock view", async () => {
    api.fetchStockVerdict.mockResolvedValue({
      call: "leans_short", score: -0.4, parts: {}, computed_at: "2026-10-20T14:00:00Z",
      reasons: ["Below 4 of 5 trend lines", "Volume heavier on down bars"],
    });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    expect(await screen.findByText("Leans short")).toBeInTheDocument();
    expect(screen.getByText("Volume heavier on down bars")).toBeInTheDocument();
    expect(screen.getByText(/^Scored /)).toBeInTheDocument();
  });

  it("ignores a late response for a ticker that is no longer selected", async () => {
    let finishHost: (value: unknown) => void = () => {};
    api.fetchStockSetups.mockImplementation((ticker: string) =>
      ticker === "HOST"
        ? new Promise((resolve) => (finishHost = resolve))
        : Promise.resolve({ setups: [{ ...SETUP, id: 9, ticker: "WORX", pattern: "abcd" }], warnings: [],
            show_short_setups: false }),
    );
    const { rerender } = render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    rerender(<StockView ticker="WORX" onTickerChange={vi.fn()} />);
    expect(await screen.findByRole("button", { name: /ABCD/ })).toBeInTheDocument();

    finishHost({ setups: [SETUP], warnings: [], show_short_setups: false });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.queryByRole("button", { name: /Bull flag/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ABCD/ })).toBeInTheDocument();
  });

  it("drops a scan's results if the ticker changed while it ran", async () => {
    let finishScan: (value: unknown) => void = () => {};
    api.runScan.mockImplementation(() => new Promise((resolve) => (finishScan = resolve)));
    api.fetchStockSetups.mockImplementation((ticker: string) =>
      Promise.resolve({
        setups: [ticker === "HOST" ? SETUP : { ...SETUP, id: 9, ticker: "WORX", pattern: "abcd" }],
        warnings: [], show_short_setups: false,
      }),
    );
    const { rerender } = render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Scan this stock" }));

    rerender(<StockView ticker="WORX" onTickerChange={vi.fn()} />);
    expect(await screen.findByRole("button", { name: /ABCD/ })).toBeInTheDocument();
    finishScan({ scanned: ["HOST"], failed: [], setups_found: 1, scanned_at: "x" });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.queryByRole("button", { name: /Bull flag/ })).not.toBeInTheDocument();
  });
});
