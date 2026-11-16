import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { JournalSummary } from "../api/journal";
import { passEntry, tradeEntry } from "../test/journalFixtures";
import { JournalView } from "./JournalView";

const api = vi.hoisted(() => ({
  fetchSummary: vi.fn(),
  fetchEntries: vi.fn(),
  fetchReasons: vi.fn(),
  fetchJournalSettings: vi.fn(),
  saveJournalSettings: vi.fn(),
  detailProps: [] as { entry: { id: number } }[],
}));
vi.mock("../api/journal", () => ({
  fetchSummary: (period: string) => api.fetchSummary(period),
  fetchEntries: (kind: string | null, period: string) => api.fetchEntries(kind, period),
  fetchReasons: () => api.fetchReasons(),
  exportUrl: (kind: string, period: string) => `/export/${kind}?${period}`,
}));
vi.mock("../api/settings", () => ({
  fetchJournalSettings: () => api.fetchJournalSettings(),
  saveJournalSettings: (settings: unknown) => api.saveJournalSettings(settings),
}));
vi.mock("./DailyLossBanner", () => ({ DailyLossBanner: () => null }));
vi.mock("./PnlChart", () => ({ PnlChart: () => <div data-testid="pnl-chart" /> }));
vi.mock("./JournalEntryDetail", () => ({
  JournalEntryDetail: (props: { entry: { id: number } }) => {
    api.detailProps.push(props);
    return <article aria-label="entry detail" />;
  },
}));

const SUMMARY: JournalSummary = {
  net_pnl: 105, trades: 1, wins: 1, losses: 0, win_rate: 1, average_gain: 105, average_loss: null, largest_win: 105,
  largest_loss: null, average_planned_reward_risk: 3, average_r: 2.63, average_duration_seconds: 1200,
  average_sykes_points: 10, average_sykes_letter: "B", average_score: 80, average_left_on_table_r: 1.4, passes: 1,
  open_trades: 0, pnl_points: [{ time: "2026-11-09T10:05:00-05:00", pnl: 105, cumulative: 105 }],
  by_country: [{ label: "USA", count: 1, pnl: 105 }], by_industry: [{ label: "Software", count: 1, pnl: 105 }],
  by_pattern: [{ label: "bull_flag", count: 1, pnl: 105 }], by_mistake: [{ label: "chased", count: 1, pnl: 105 }],
  by_time_of_day: [{ label: "9:30–10", count: 1, pnl: 105 }], by_duration: [{ label: "5–30 min", count: 1, pnl: 105 }],
  pass_reasons: [{
    reason: "low_sykes", count: 1, target: 0, stop: 1, never_filled: 0, undecided: 0, already_past: 0, average_r: -1,
    average_best_percent: 5.5, average_worst_percent: -3.25,
  }],
  versus_system: [{ pattern: "bull_flag", timeframe: "5m", trades: 1, win_rate: 1, average_r: 2.63,
    system: { trades: 40, win_rate: 0.22, average_r: -0.2 }, system_has_enough_history: true }],
};
const CATALOG = {
  pass_reasons: [
    { group: "The app's read", items: [{ key: "low_sykes", label: "Low Sykes grade" }] },
    { group: "Timing", items: [{ key: "too_late", label: "Too late / extended" }] },
  ],
  mistakes: [{ key: "chased", label: "Chased" }],
};

describe("JournalView", () => {
  beforeEach(() => {
    api.fetchSummary.mockResolvedValue(SUMMARY);
    api.fetchEntries.mockResolvedValue([tradeEntry(), passEntry()]);
    api.fetchReasons.mockResolvedValue(CATALOG);
    api.fetchJournalSettings.mockResolvedValue({ risk_per_trade: null, max_position: null, max_daily_loss: null });
    api.saveJournalSettings.mockImplementation((settings: unknown) => Promise.resolve(settings));
    api.detailProps = [];
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows this week's summary and entries by default", async () => {
    render(<JournalView onOpenStock={vi.fn()} />);

    expect((await screen.findByText("Net P&L")).parentElement).toHaveTextContent("+$105.00");
    expect(api.fetchSummary).toHaveBeenCalledWith("week");
    expect(api.fetchEntries).toHaveBeenCalledWith(null, "week");
    expect(screen.getByTestId("pnl-chart")).toBeInTheDocument();
    expect(screen.getByText("B · 10.0/14")).toBeInTheDocument();
    expect(document.title).toBe("Journal · +$105.00 this week · Finviz");
  });

  it("reloads for another period", async () => {
    render(<JournalView onOpenStock={vi.fn()} />);
    await screen.findByText("Net P&L");

    fireEvent.click(screen.getByRole("button", { name: "This month" }));

    await vi.waitFor(() => expect(api.fetchSummary).toHaveBeenCalledWith("month"));
    expect(api.fetchEntries).toHaveBeenLastCalledWith(null, "month");
  });

  it("lists trades with P&L and R, and passes with their reasons", async () => {
    render(<JournalView onOpenStock={vi.fn()} />);

    const list = await screen.findByRole("table", { name: "Journal entries" });
    await within(list).findByText("+2.63R");
    const rows = within(list).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("+$105.00");
    expect(rows[1]).toHaveTextContent("+2.63R");
    expect(rows[2]).toHaveTextContent("Low Sykes grade, Too late / extended");
  });

  it("shows only trades or only passes", async () => {
    render(<JournalView onOpenStock={vi.fn()} />);
    await screen.findByRole("table", { name: "Journal entries" });

    fireEvent.click(screen.getByRole("button", { name: "Passes" }));

    await vi.waitFor(() => expect(api.fetchEntries).toHaveBeenLastCalledWith("pass", "week"));
  });

  it("opens an entry's detail", async () => {
    render(<JournalView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Open HOST trade" }));

    expect(await screen.findByRole("article", { name: "entry detail" })).toBeInTheDocument();
    expect(api.detailProps[api.detailProps.length - 1].entry.id).toBe(3);
  });

  it("shows breakdowns with labels", async () => {
    render(<JournalView onOpenStock={vi.fn()} />);

    const mistakes = await screen.findByRole("table", { name: "By mistake" });
    expect(mistakes).toHaveTextContent("Chased");
    expect(screen.getByRole("table", { name: "By pattern" })).toHaveTextContent("Bull flag");
    expect(screen.getByRole("table", { name: "You vs. the system" })).toHaveTextContent("−0.20R");
    const passes = screen.getByRole("table", { name: "Passes by reason" });
    expect(passes).toHaveTextContent("+5.50%");
    expect(passes).toHaveTextContent("-3.25%");
  });

  it("links the CSV exports for the period", async () => {
    render(<JournalView onOpenStock={vi.fn()} />);

    expect(await screen.findByRole("link", { name: "Export entries (CSV)" })).toHaveAttribute("href", "/export/entries?week");
    expect(screen.getByRole("link", { name: "Export fills (CSV)" })).toHaveAttribute("href", "/export/fills?week");
  });

  it("saves the risk settings", async () => {
    render(<JournalView onOpenStock={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Risk settings" }));

    fireEvent.change(screen.getByLabelText("Risk per trade ($)"), { target: { value: "50" } });
    fireEvent.change(screen.getByLabelText("Max daily loss ($)"), { target: { value: "200" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));

    await vi.waitFor(() =>
      expect(api.saveJournalSettings).toHaveBeenCalledWith({ risk_per_trade: 50, max_position: null, max_daily_loss: 200 }),
    );
  });
});
