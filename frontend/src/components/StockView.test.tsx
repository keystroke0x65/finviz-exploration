import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Setup } from "../api/setups";
import { StockView } from "./StockView";

const api = vi.hoisted(() => ({
  fetchBars: vi.fn(),
  fetchStockSetups: vi.fn(),
  fetchStockVerdict: vi.fn(),
  runScan: vi.fn(),
  fetchQuote: vi.fn(),
  refreshQuote: vi.fn(),
  chartProps: [] as ChartProps[],
  fetchNews: vi.fn(),
  fetchOpenTrade: vi.fn(),
  fetchEntries: vi.fn(),
  fetchJournalSettings: vi.fn(),
  tradePanelProps: [] as { existing: unknown; clickedBar: unknown; preferredSetupId: number | null }[],
}));
vi.mock("../api/journal", () => ({
  fetchOpenTrade: (ticker: string) => api.fetchOpenTrade(ticker),
  fetchEntries: (...args: unknown[]) => api.fetchEntries(...args),
}));
vi.mock("../api/settings", () => ({ fetchJournalSettings: () => api.fetchJournalSettings() }));
vi.mock("./DailyLossBanner", () => ({ DailyLossBanner: () => null }));
vi.mock("./TradePanel", () => ({
  TradePanel: (props: { existing: unknown; clickedBar: unknown; preferredSetupId: number | null; onClose: () => void }) => {
    api.tradePanelProps.push(props);
    return (
      <section aria-label="trade panel">
        <button type="button" onClick={props.onClose}>Close trade panel</button>
      </section>
    );
  },
}));
vi.mock("./PassPanel", () => ({ PassPanel: () => <section aria-label="pass panel" /> }));
vi.mock("../api/bars", () => ({ fetchBars: (...args: unknown[]) => api.fetchBars(...args) }));
vi.mock("../api/setups", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/setups")>()),
  fetchStockSetups: (ticker: string) => api.fetchStockSetups(ticker),
  fetchStockVerdict: (ticker: string) => api.fetchStockVerdict(ticker),
  runScan: (ticker?: string) => api.runScan(ticker),
}));
vi.mock("../api/stocks", () => ({
  fetchQuote: (ticker: string) => api.fetchQuote(ticker),
  refreshQuote: (ticker: string) => api.refreshQuote(ticker),
  fetchNews: (ticker: string, refresh?: boolean) => api.fetchNews(ticker, refresh),
}));
interface ChartProps {
  levels: { price: number; kind: string }[];
  shadeSessions?: boolean;
  markers?: { side: string; shares: number }[];
  news?: { title: string }[];
  onBarClick?: (bar: unknown) => void;
}
vi.mock("./CandleChart", () => ({
  CandleChart: (props: ChartProps) => {
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
    api.refreshQuote.mockResolvedValue({ Ticker: "HOST", Company: "Host Digital Inc" });
    api.fetchStockVerdict.mockResolvedValue(null);
    api.fetchNews.mockResolvedValue([]);
    api.fetchOpenTrade.mockResolvedValue(null);
    api.fetchEntries.mockResolvedValue([]);
    api.fetchJournalSettings.mockResolvedValue({ risk_per_trade: null, max_position: null, max_daily_loss: null });
    api.chartProps = [];
    api.tradePanelProps = [];
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("titles the browser tab with the ticker, price and change", async () => {
    api.fetchQuote.mockResolvedValue({ Ticker: "HOST", Price: "2.15", Change: "12.30%" });

    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    await vi.waitFor(() => expect(document.title).toBe("HOST 2.15 +12.30% · Finviz"));
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

  it("lists each setup's entry, stop, target, reward:risk and risk", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    const setupButton = await screen.findByRole("button", { name: /Bull flag/ });
    expect(within(setupButton).getByText("Entry").nextElementSibling).toHaveTextContent("2.12");
    expect(within(setupButton).getByText("Stop").nextElementSibling).toHaveTextContent("2.05");
    expect(within(setupButton).getByText("Target").nextElementSibling).toHaveTextContent("2.33");
    expect(within(setupButton).getByText("3.0R · risk 3.3%")).toBeInTheDocument();
  });

  it("says when a nearby level caps the target", async () => {
    api.fetchStockSetups.mockResolvedValue({
      setups: [{ ...SETUP, blocking_level: 2.3, capped_target: 2.3, available_reward_risk: 2.6 }], warnings: [],
      show_short_setups: false,
    });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    const setupButton = await screen.findByRole("button", { name: /Bull flag/ });
    expect(within(setupButton).getByText("Target (capped)").nextElementSibling).toHaveTextContent("2.30");
    expect(within(setupButton).getByText("2.6R · risk 3.3%")).toBeInTheDocument();
  });

  it("shows each setup's score and Sykes grade, with the grade's factors on hover", async () => {
    api.fetchStockSetups.mockResolvedValue({
      setups: [{
        ...SETUP,
        sliding_scale: { letter: "B", points: 10, factors: [{ name: "Risk/reward", grade: "good", detail: "3.0R (wants 3R+)" }] },
      }],
      warnings: [], show_short_setups: false,
    });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    const setupItem = (await screen.findByRole("button", { name: /Bull flag/ })).closest("li")!;
    expect(within(setupItem).getByText("Score").nextElementSibling).toHaveTextContent("80");
    const grade = within(setupItem).getByRole("button", { name: "Sykes sliding scale B for HOST" });
    fireEvent.mouseEnter(grade);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Sykes sliding scale: B (10/14)");
    expect(screen.getByRole("tooltip")).toHaveTextContent("3.0R (wants 3R+)");
  });

  it("shows a dash for a setup not graded on the Sykes scale yet", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    const setupItem = (await screen.findByRole("button", { name: /Bull flag/ })).closest("li")!;
    expect(within(setupItem).getByText("Sykes").nextElementSibling).toHaveTextContent("—");
    expect(within(setupItem).queryByRole("button", { name: /Sykes sliding scale/ })).not.toBeInTheDocument();
  });

  it("shows a bearish warning's breakdown level instead of a trade plan", async () => {
    api.fetchStockSetups.mockResolvedValue({
      setups: [], show_short_setups: false,
      warnings: [{
        id: 3, ticker: "HOST", pattern: "bear_flag", direction: "short", timeframe: "5m", entry: 1.98,
        state: "forming", triggered_at: null, key_points: [], detected_at: SETUP.detected_at,
        last_seen_at: SETUP.last_seen_at,
      }],
    });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    const warningButton = await screen.findByRole("button", { name: /Bear flag/ });
    expect(within(warningButton).getByText("Bearish warning, breaks below 1.98")).toBeInTheDocument();
    expect(within(warningButton).queryByText("Target")).not.toBeInTheDocument();
    // Warnings aren't scored or graded.
    expect(within(warningButton.closest("li")!).queryByText("Score")).not.toBeInTheDocument();
  });

  it("reloads the chart and quote after a scan", async () => {
    api.runScan.mockResolvedValue({ scanned: ["HOST"], failed: [], setups_found: 1, scanned_at: "x" });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "1m" }));
    await screen.findByTestId("chart");
    api.fetchBars.mockResolvedValue({ ...BARS_RESPONSE, fetched_at: "2026-10-20T13:41:00Z" });
    api.refreshQuote.mockResolvedValue({ Ticker: "HOST", Company: "Host Digital Inc", Price: "2.40" });

    fireEvent.click(screen.getByRole("button", { name: "Scan this stock" }));

    expect(await screen.findByText("2.40")).toBeInTheDocument();
    await vi.waitFor(() => expect(api.fetchBars).toHaveBeenLastCalledWith("HOST", "1m"));
    const expectedTime = new Date("2026-10-20T13:41:00Z").toLocaleTimeString();
    expect(await screen.findByText(`Bars as of ${expectedTime}`)).toBeInTheDocument();
    expect(api.refreshQuote).toHaveBeenCalledWith("HOST");
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


describe("StockView journal", () => {
  beforeEach(() => {
    api.fetchBars.mockResolvedValue(BARS_RESPONSE);
    api.fetchStockSetups.mockResolvedValue({ setups: [SETUP], warnings: [], show_short_setups: false });
    api.fetchQuote.mockResolvedValue({ Ticker: "HOST" });
    api.fetchStockVerdict.mockResolvedValue(null);
    api.fetchNews.mockResolvedValue([]);
    api.fetchOpenTrade.mockResolvedValue(null);
    api.fetchEntries.mockResolvedValue([]);
    api.fetchJournalSettings.mockResolvedValue({ risk_per_trade: null, max_position: null, max_daily_loss: null });
    api.chartProps = [];
    api.tradePanelProps = [];
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("opens the trade panel with L, the pass panel with P, and closes with Escape", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    await screen.findByTestId("chart");

    fireEvent.keyDown(window, { key: "l" });
    expect(await screen.findByRole("region", { name: "trade panel" })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    await vi.waitFor(() => expect(screen.queryByRole("region", { name: "trade panel" })).not.toBeInTheDocument());

    fireEvent.keyDown(window, { key: "p" });
    expect(await screen.findByRole("region", { name: "pass panel" })).toBeInTheDocument();
  });

  it("keeps the panel open when Escape is pressed while typing", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    await screen.findByTestId("chart");
    fireEvent.keyDown(window, { key: "l" });
    await screen.findByRole("region", { name: "trade panel" });

    fireEvent.keyDown(screen.getByLabelText("Stock ticker"), { key: "Escape" });

    expect(screen.getByRole("region", { name: "trade panel" })).toBeInTheDocument();
  });

  it("starts a new trade without replaying the last candle click", async () => {
    api.fetchOpenTrade.mockResolvedValue({ id: 4, ticker: "HOST", fills: [], decided_at: "2026-10-19T14:00:00Z" });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    await screen.findByTestId("chart");
    fireEvent.click(screen.getByRole("button", { name: "Log trade" }));
    await screen.findByRole("region", { name: "trade panel" });
    act(() => api.chartProps[api.chartProps.length - 1].onBarClick?.(BARS_RESPONSE.bars[0]));

    fireEvent.click(screen.getByRole("button", { name: "Start a new trade instead" }));

    await vi.waitFor(() => expect(api.tradePanelProps[api.tradePanelProps.length - 1].existing).toBeNull());
    expect(api.tradePanelProps[api.tradePanelProps.length - 1].clickedBar).toBeNull();
  });

  it("doesn't take fills from the daily chart", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    await screen.findByTestId("chart");
    fireEvent.click(screen.getByRole("button", { name: "daily" }));

    await vi.waitFor(() => expect(api.fetchBars).toHaveBeenCalledWith("HOST", "daily"));
    await vi.waitFor(() => expect(api.chartProps[api.chartProps.length - 1].onBarClick).toBeUndefined());
  });

  it("ignores shortcuts while typing", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    await screen.findByTestId("chart");

    fireEvent.keyDown(screen.getByLabelText("Stock ticker"), { key: "l" });

    expect(screen.queryByRole("region", { name: "trade panel" })).not.toBeInTheDocument();
  });

  it("hands clicked candles to the open trade panel", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    await screen.findByTestId("chart");
    fireEvent.click(await screen.findByRole("button", { name: /Bull flag/ }));

    fireEvent.click(screen.getByRole("button", { name: "Log trade" }));
    await screen.findByRole("region", { name: "trade panel" });
    const bar = BARS_RESPONSE.bars[0];
    act(() => api.chartProps[api.chartProps.length - 1].onBarClick?.(bar));

    await vi.waitFor(() =>
      expect(api.tradePanelProps[api.tradePanelProps.length - 1].clickedBar).toEqual({ bar, id: 1 }),
    );
    // The setup picked in the side list is the panel's first choice if it fits the trade.
    expect(api.tradePanelProps[0].preferredSetupId).toBe(7);
  });

  it("continues the stock's open trade, or starts a new one", async () => {
    const openTrade = { id: 4, ticker: "HOST", fills: [] };
    api.fetchOpenTrade.mockResolvedValue(openTrade);
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    await screen.findByTestId("chart");

    fireEvent.click(screen.getByRole("button", { name: "Log trade" }));
    await screen.findByRole("region", { name: "trade panel" });
    expect(api.tradePanelProps[api.tradePanelProps.length - 1].existing).toEqual(openTrade);

    fireEvent.click(screen.getByRole("button", { name: "Start a new trade instead" }));

    await vi.waitFor(() => expect(api.tradePanelProps[api.tradePanelProps.length - 1].existing).toBeNull());
  });

  it("marks this stock's logged fills on the chart", async () => {
    api.fetchEntries.mockResolvedValue([
      { ticker: "HOST", fills: [{ side: "buy", time: "2026-10-20T09:30:00-04:00", price: 2, shares: 100 }] },
    ]);
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    await vi.waitFor(() => expect(api.fetchEntries).toHaveBeenCalledWith("trade", "all", "HOST"));
    await vi.waitFor(() =>
      expect(api.chartProps[api.chartProps.length - 1].markers).toEqual([
        { side: "buy", time: "2026-10-20T09:30:00-04:00", price: 2, shares: 100 },
      ]),
    );
  });

  it("suggests a position size on each setup when a risk amount is set", async () => {
    api.fetchJournalSettings.mockResolvedValue({ risk_per_trade: 50, max_position: null, max_daily_loss: null });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    expect(await screen.findByText("Size 714 sh ($1,513.68) to risk $50.00")).toBeInTheDocument();
  });
});


describe("StockView news", () => {
  // Recent, so it falls in the list's first 2 weeks.
  const NEWS = [{ time: new Date(Date.now() - 3_600_000).toISOString(), source: "GlobeNewswire", title: "Host wins contract", url: "https://example.com/a" }];

  beforeEach(() => {
    api.fetchBars.mockResolvedValue(BARS_RESPONSE);
    api.fetchStockSetups.mockResolvedValue({ setups: [SETUP], warnings: [], show_short_setups: false });
    api.fetchQuote.mockResolvedValue({ Ticker: "HOST" });
    api.refreshQuote.mockResolvedValue({ Ticker: "HOST" });
    api.fetchStockVerdict.mockResolvedValue(null);
    api.fetchOpenTrade.mockResolvedValue(null);
    api.fetchEntries.mockResolvedValue([]);
    api.fetchJournalSettings.mockResolvedValue({ risk_per_trade: null, max_position: null, max_daily_loss: null });
    api.fetchNews.mockResolvedValue(NEWS);
    api.chartProps = [];
    api.tradePanelProps = [];
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("lists the stock's news under the chart and marks it on the chart", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    expect(await screen.findByRole("link", { name: "Host wins contract" })).toBeInTheDocument();
    expect(api.fetchNews).toHaveBeenCalledWith("HOST", undefined);
    await vi.waitFor(() => expect(api.chartProps[api.chartProps.length - 1].news).toEqual(NEWS));
  });

  it("opens the trade panel between the chart and the news, and only when asked", async () => {
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);
    const news = await screen.findByRole("region", { name: "News" });
    expect(screen.queryByRole("region", { name: "trade panel" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Log trade" }));

    const panel = await screen.findByRole("region", { name: "trade panel" });
    expect(panel.compareDocumentPosition(news) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByTestId("chart").compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("refreshes the news when the stock is scanned", async () => {
    api.runScan.mockResolvedValue({ scanned: ["HOST"], failed: [], setups_found: 0, scanned_at: "x" });
    render(<StockView ticker="HOST" onTickerChange={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Scan this stock" }));

    await vi.waitFor(() => expect(api.fetchNews).toHaveBeenCalledWith("HOST", true));
  });
});
