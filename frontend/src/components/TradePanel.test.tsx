import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Bar } from "../api/bars";
import type { DaySetup, JournalEntry } from "../api/journal";
import { TradePanel } from "./TradePanel";

const api = vi.hoisted(() => ({
  fetchDaySetups: vi.fn(),
  fetchReasons: vi.fn(),
  createEntry: vi.fn(),
  updateEntry: vi.fn(),
  previewTrade: vi.fn(),
}));
vi.mock("../api/journal", () => ({
  fetchDaySetups: (...args: unknown[]) => api.fetchDaySetups(...args),
  fetchReasons: () => api.fetchReasons(),
  createEntry: (draft: unknown) => api.createEntry(draft),
  updateEntry: (id: number, draft: unknown) => api.updateEntry(id, draft),
  previewTrade: (draft: unknown) => api.previewTrade(draft),
}));

const SETUP: DaySetup = {
  setup_record_id: 7, detected_at: "2026-11-09T09:30:00-05:00", triggered_at: "2026-11-09T09:44:00-05:00", pattern: "bull_flag", timeframe: "5m", direction: "long", entry: 1.84, stop: 1.76, target: 2.08,
  reward_risk: 3, score: 80, state: "forming", verdict: null, sliding_scale: null, outcome: "open",
};
const OTHER_SETUP: DaySetup = {
  ...SETUP, setup_record_id: 9, pattern: "bear_flag", direction: "short", entry: 1.7, stop: 1.8, target: 1.4,
};
const BAR: Bar = { time: "2026-11-09T09:45:00-05:00", open: 1.8, high: 1.86, low: 1.79, close: 1.84, volume: 1000 };
const LATER_BAR: Bar = { time: "2026-11-09T10:05:00-05:00", open: 2.0, high: 2.1, low: 1.98, close: 2.05, volume: 900 };
const FIGURES = {
  status: "closed", first_price: 1.84, average_entry: 1.84, average_exit: 2.05, shares_held: 0, max_shares: 500,
  money_in: 920, total_bought: 920, realised_pnl: 105, closed_pnl: [], fees: 0, net_pnl: 105, r_multiple: 2.625,
  planned_reward_risk: 3, opened_at: BAR.time, last_fill_at: LATER_BAR.time, duration_seconds: 1200,
};
const NO_FACTS = {
  company: null, country: null, sector: null, industry: null, market_cap_millions: null, float_millions: null,
  price: null, change_percent: null, volume_so_far: null, volume_vs_average: null,
};
const NO_SETTINGS = { risk_per_trade: null, max_position: null, max_daily_loss: null };

function renderPanel(props: Partial<Parameters<typeof TradePanel>[0]> = {}) {
  const defaults = {
    ticker: "HOST", preferredSetupId: null, existing: null, settings: NO_SETTINGS, clickedBar: null,
    onSaved: vi.fn(), onClose: vi.fn(),
  };
  const merged = { ...defaults, ...props };
  const view = render(<TradePanel {...merged} />);
  return { ...view, props: merged };
}

function fillRows() {
  return screen.getAllByRole("group", { name: /^Fill \d+$/ });
}

describe("TradePanel", () => {
  beforeEach(() => {
    api.fetchReasons.mockResolvedValue({ pass_reasons: [], mistakes: [{ key: "chased", label: "Chased" }] });
    api.fetchDaySetups.mockResolvedValue({ matches: [SETUP], others: [OTHER_SETUP] });
    api.previewTrade.mockResolvedValue({ figures: null, error: "Add at least one fill." });
    api.createEntry.mockResolvedValue({ id: 3, kind: "trade", bar_warning: null });
    api.updateEntry.mockResolvedValue({ id: 3, kind: "trade", bar_warning: null });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("picks the best matching setup and fills the plan from it", async () => {
    renderPanel();

    await vi.waitFor(() => expect(screen.getByLabelText("Plan stop")).toHaveValue(1.76));
    expect(screen.getByLabelText("Plan target")).toHaveValue(2.08);
    expect(screen.getByRole("combobox", { name: "Setup" })).toHaveValue("7");
  });

  it("asks for the setups that fit the first fill", async () => {
    const { rerender, props } = renderPanel();
    rerender(<TradePanel {...props} clickedBar={{ bar: BAR, id: 1 }} />);

    await vi.waitFor(() =>
      expect(api.fetchDaySetups).toHaveBeenLastCalledWith("HOST", "2026-11-09", "2026-11-09T09:45:00-05:00", "long", 1.84),
    );
    expect(await screen.findByRole("group", { name: "Best matches for your 9:45 AM buy at 1.84" })).toBeInTheDocument();
  });

  it("keeps a setup the user chose when the matches change", async () => {
    const { rerender, props } = renderPanel();
    await vi.waitFor(() => expect(screen.getByRole("combobox", { name: "Setup" })).toHaveValue("7"));

    fireEvent.change(screen.getByRole("combobox", { name: "Setup" }), { target: { value: "9" } });
    rerender(<TradePanel {...props} clickedBar={{ bar: BAR, id: 1 }} />);
    await vi.waitFor(() => expect(api.fetchDaySetups.mock.calls.length).toBeGreaterThan(1));

    expect(screen.getByRole("combobox", { name: "Setup" })).toHaveValue("9");
  });

  it("adds a buy and then a sell from clicked candles", () => {
    const { rerender, props } = renderPanel();

    rerender(<TradePanel {...props} clickedBar={{ bar: BAR, id: 1 }} />);
    fireEvent.change(within(fillRows()[0]).getByLabelText("Shares"), { target: { value: "500" } });
    rerender(<TradePanel {...props} clickedBar={{ bar: LATER_BAR, id: 2 }} />);

    const [first, second] = fillRows();
    expect(within(first).getByLabelText("Side")).toHaveValue("buy");
    expect(within(first).getByLabelText("Time (ET)")).toHaveValue("09:45");
    expect(within(first).getByLabelText("Price")).toHaveValue(1.84);
    expect(within(second).getByLabelText("Side")).toHaveValue("sell");
    expect(within(second).getByLabelText("Shares")).toHaveValue(500);
  });

  it("warns when a price is outside the clicked candle", () => {
    const { rerender, props } = renderPanel();
    rerender(<TradePanel {...props} clickedBar={{ bar: BAR, id: 1 }} />);

    fireEvent.change(within(fillRows()[0]).getByLabelText("Price"), { target: { value: "1.95" } });

    expect(screen.getByText("Price is outside that candle's range (1.79–1.86).")).toBeInTheDocument();
  });

  it("previews the figures for typed fills", async () => {
    api.previewTrade.mockResolvedValue({ figures: FIGURES, error: null });
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Add fill" }));
    const row = fillRows()[0];
    fireEvent.change(within(row).getByLabelText("Date"), { target: { value: "2026-11-09" } });
    fireEvent.change(within(row).getByLabelText("Time (ET)"), { target: { value: "09:45" } });
    fireEvent.change(within(row).getByLabelText("Price"), { target: { value: "1.84" } });
    fireEvent.change(within(row).getByLabelText("Shares"), { target: { value: "500" } });

    expect(await screen.findByText("+$105.00")).toBeInTheDocument();
    // The matching setup arrives a moment after the fill, and the preview follows it.
    await vi.waitFor(() =>
      expect(api.previewTrade).toHaveBeenLastCalledWith(
        expect.objectContaining({
          fills: [{ side: "buy", time: "2026-11-09T09:45:00-05:00", price: 1.84, shares: 500 }],
          plan_stop: 1.76,
          setup_record_id: 7,
        }),
      ),
    );
  });

  it("shows the preview's problem with the fills", async () => {
    api.previewTrade.mockResolvedValue({ figures: null, error: "The first fill must be a buy for a long trade." });
    const { rerender, props } = renderPanel();
    rerender(<TradePanel {...props} clickedBar={{ bar: BAR, id: 1 }} />);
    fireEvent.change(within(fillRows()[0]).getByLabelText("Side"), { target: { value: "sell" } });
    fireEvent.change(within(fillRows()[0]).getByLabelText("Shares"), { target: { value: "100" } });

    expect(await screen.findByText("The first fill must be a buy for a long trade.")).toBeInTheDocument();
  });

  it("suggests a position size from the risk setting", async () => {
    renderPanel({ settings: { risk_per_trade: 50, max_position: null, max_daily_loss: null } });

    expect(await screen.findByText("Size 625 sh ($1,150.00) to risk $50.00")).toBeInTheDocument();
  });

  it("saves a new trade", async () => {
    const { rerender, props } = renderPanel();
    rerender(<TradePanel {...props} clickedBar={{ bar: BAR, id: 1 }} />);
    fireEvent.change(within(fillRows()[0]).getByLabelText("Shares"), { target: { value: "500" } });
    fireEvent.click(await screen.findByRole("button", { name: "Chased" }));
    await vi.waitFor(() => expect(screen.getByLabelText("Plan stop")).toHaveValue(1.76));

    fireEvent.click(screen.getByRole("button", { name: "Save trade" }));

    await vi.waitFor(() => expect(props.onSaved).toHaveBeenCalled());
    expect(api.createEntry).toHaveBeenCalledWith({
      kind: "trade", ticker: "HOST", direction: "long", setup_record_id: 7, plan_stop: 1.76, plan_target: 2.08,
      fees: 0, mistakes: ["chased"], note: "",
      fills: [{ side: "buy", time: "2026-11-09T09:45:00-05:00", price: 1.84, shares: 500 }],
    });
  });

  it("adds fills to an open trade and saves it in place", async () => {
    const existing: JournalEntry = {
      id: 3, kind: "trade", ticker: "HOST", direction: "long", created_at: BAR.time, updated_at: BAR.time,
      decided_at: BAR.time, setup: { ...SETUP, sliding_scale: null }, stock: NO_FACTS, plan_stop: 1.76,
      plan_target: 2.08, fees: 0, reasons: [], mistakes: [], note: "", pass_price: null,
      fills: [{ side: "buy", time: BAR.time, price: 1.84, shares: 500 }], figures: null, after_exit: null,
      plan_flags: [], pass_score: null, after_pass: null, bar_warning: null,
    };
    const { rerender, props } = renderPanel({ existing });
    rerender(<TradePanel {...props} clickedBar={{ bar: LATER_BAR, id: 1 }} />);

    fireEvent.click(screen.getByRole("button", { name: "Save trade" }));

    await vi.waitFor(() => expect(api.updateEntry).toHaveBeenCalled());
    expect(api.updateEntry.mock.calls[0][0]).toBe(3);
    expect(api.updateEntry.mock.calls[0][1].fills).toEqual([
      { side: "buy", time: "2026-11-09T09:45:00-05:00", price: 1.84, shares: 500 },
      { side: "sell", time: "2026-11-09T10:05:00-05:00", price: 2.05, shares: 500 },
    ]);
  });
});
