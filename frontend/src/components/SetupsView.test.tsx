import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ScanStatus, Setup, TrackRecordSummary, Warning } from "../api/setups";
import { SetupsView } from "./SetupsView";

const CLEAN_SCAN: ScanStatus = {
  latest: { status: "completed", finished_at: "2026-10-20T10:45:00-04:00", scanned: 40, failed: [] },
  last_completed_at: "2026-10-20T10:45:00-04:00",
  is_overdue: false,
};
const api = {
  fetchSetups: vi.fn(),
  runScan: vi.fn(),
  saveSettings: vi.fn(),
  fetchScanStatus: vi.fn(() => Promise.resolve(CLEAN_SCAN)),
};
vi.mock("../api/setups", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/setups")>()),
  fetchSetups: () => api.fetchSetups(),
  runScan: (ticker?: string) => api.runScan(ticker),
  fetchScanStatus: () => api.fetchScanStatus(),
}));
vi.mock("../api/settings", () => ({ saveSettings: (settings: unknown) => api.saveSettings(settings) }));

function setup(overrides: Partial<Setup> = {}): Setup {
  return {
    id: 1, ticker: "HOST", pattern: "bull_flag", direction: "long", timeframe: "5m", entry: 2.0, stop: 1.9,
    capped_target: 2.3, target_3r: 2.3, available_reward_risk: 3.0, risk_percent: 5.0, blocking_level: null,
    partial_1r: 2.1, partial_2r: 2.2, trailing_stop: null, quality: 0.7, score: 81.5,
    score_parts: { reward_risk: 40, quality: 17.5, volume: 10, freshness: 10, timeframe_agreement: 0, conflict: 0 },
    key_points: [], state: "forming", triggered_at: null, session: "regular", detected_at: "2026-10-20T14:00:00Z",
    last_seen_at: "2026-10-20T14:00:30Z", has_conflict: false, ...overrides,
  };
}

function respond(setups: Setup[], warnings: Warning[] = [], showShorts = false) {
  api.fetchSetups.mockResolvedValue({ setups, warnings, show_short_setups: showShorts });
}

function history(overrides: Partial<TrackRecordSummary>): TrackRecordSummary {
  return {
    trades: 42, win_rate: 20 / 42, average_r: 0.31, average_win_r: 2.1, tickers: 15, trading_days: 9,
    has_enough_history: true, ...overrides,
  };
}

describe("SetupsView", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows each setup's Sykes sliding scale grade next to its score", async () => {
    respond([
      setup({
        sliding_scale: {
          letter: "B", points: 10,
          factors: [
            { name: "Risk/reward", grade: "good", detail: "3.0R (wants 3R+)" },
            { name: "Time", grade: "poor", detail: "Pre-market (7:05 AM)" },
            { name: "Market", grade: "no_data", detail: "No market data" },
          ],
        },
      }),
      setup({ id: 2, ticker: "WORX", sliding_scale: null }),
    ]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    const headers = (await screen.findAllByRole("columnheader")).map((header) => header.textContent);
    expect(headers.slice(-2)).toEqual(["Score", "Sykes"]);
    const grade = screen.getByRole("button", { name: "Sykes sliding scale B for HOST" });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    fireEvent.mouseEnter(grade);
    const card = screen.getByRole("tooltip");
    expect(card).toHaveTextContent("Sykes sliding scale: B (10/14)");
    expect(within(card).getByText("Risk/reward").closest("li")).toHaveTextContent("3.0R (wants 3R+)");
    expect(within(card).getByText("Time").closest("li")).toHaveAttribute("data-grade", "poor");
    expect(within(card).getByText("Market").closest("li")).toHaveTextContent("No market data");

    fireEvent.mouseLeave(grade);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("opens the sliding scale card from the keyboard too", async () => {
    respond([setup({ sliding_scale: { letter: "A", points: 13, factors: [] } })]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    fireEvent.focus(await screen.findByRole("button", { name: "Sykes sliding scale A for HOST" }));

    expect(screen.getByRole("tooltip")).toHaveTextContent("Sykes sliding scale: A (13/14)");
  });

  it("sorts by Sykes grade when its header is clicked, and back by score when clicked again", async () => {
    const graded = (letter: "A" | "B" | "C" | "D" | "F", points: number) => ({ letter, points, factors: [] });
    respond([
      setup({ id: 1, ticker: "AAA", score: 90, sliding_scale: graded("C", 8) }),
      setup({ id: 2, ticker: "BBB", score: 80, sliding_scale: null }),
      setup({ id: 3, ticker: "CCC", score: 70, sliding_scale: graded("B", 10) }),
      setup({ id: 4, ticker: "DDD", score: 60, sliding_scale: graded("B", 11) }),
      setup({ id: 5, ticker: "EEE", score: 50, sliding_scale: graded("C", 8) }),
    ]);
    render(<SetupsView onOpenStock={vi.fn()} />);
    const tickerOrder = () =>
      screen.getAllByRole("button", { name: /^Score details for/ }).map((button) =>
        (button.getAttribute("aria-label") ?? "").replace("Score details for ", ""),
      );
    expect(await screen.findByRole("button", { name: "Score details for AAA" })).toBeInTheDocument();
    expect(tickerOrder()).toEqual(["AAA", "BBB", "CCC", "DDD", "EEE"]);

    const sortButton = screen.getByRole("button", { name: "Sykes" });
    fireEvent.click(sortButton);

    // Best letter first, more points first within a letter, then score; ungraded last.
    expect(tickerOrder()).toEqual(["DDD", "CCC", "AAA", "EEE", "BBB"]);
    expect(sortButton).toHaveAttribute("aria-pressed", "true");
    expect(sortButton.closest("th")).toHaveAttribute("aria-sort", "descending");

    fireEvent.click(sortButton);

    expect(tickerOrder()).toEqual(["AAA", "BBB", "CCC", "DDD", "EEE"]);
    expect(sortButton).toHaveAttribute("aria-pressed", "false");
  });

  it("shows a dash for setups not graded yet", async () => {
    respond([setup({ sliding_scale: null })]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    const row = (await screen.findByRole("button", { name: "Score details for HOST" })).closest("tr") as HTMLElement;
    expect(row.lastElementChild).toHaveTextContent("—");
  });

  it("says when the last scan ran", async () => {
    respond([setup()]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    expect(await screen.findByText(/^Last scan .* · 40 stocks$/)).toBeInTheDocument();
  });

  it("warns when the last scan failed", async () => {
    respond([setup()]);
    api.fetchScanStatus.mockResolvedValueOnce({
      latest: { status: "crashed", finished_at: "2026-10-20T11:00:00-04:00", error_type: "TypeError" },
      last_completed_at: "2026-10-20T10:45:00-04:00",
      is_overdue: false,
    });
    render(<SetupsView onOpenStock={vi.fn()} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/scan failed \(TypeError\), so these setups are from the/);
  });

  it("checks the scan status again after scanning", async () => {
    respond([setup()]);
    api.runScan.mockResolvedValue({ scanned: ["HOST"], failed: [], setups_found: 1, scanned_at: "2026-10-20T11:00:00-04:00" });
    render(<SetupsView onOpenStock={vi.fn()} />);
    await screen.findByText(/^Last scan/);

    fireEvent.click(screen.getByRole("button", { name: "Scan watchlist" }));

    await vi.waitFor(() => expect(api.fetchScanStatus).toHaveBeenCalledTimes(2));
  });

  it("lists setups ranked with entry, stop, target and available R:R", async () => {
    respond([setup(), setup({ id: 2, ticker: "WORX", score: 55, pattern: "high_of_day_break" })]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    const rows = await screen.findAllByRole("row");
    const hostRow = rows[1];
    expect(within(hostRow).getByText("Bull flag")).toBeInTheDocument();
    expect(within(hostRow).getByText("2.00")).toBeInTheDocument();
    expect(within(hostRow).getByText("1.90")).toBeInTheDocument();
    expect(within(hostRow).getByText("2.30")).toBeInTheDocument();
    expect(within(hostRow).getByText("3.0R")).toBeInTheDocument();
    expect(within(rows[2]).getByText("High-of-day break")).toBeInTheDocument();
  });

  it("says when a triggered setup triggered", async () => {
    respond([setup({ state: "triggered", triggered_at: "2026-10-20T13:42:00Z" })]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    const [, hostRow] = await screen.findAllByRole("row");
    expect(within(hostRow).getByText("Triggered 9:42 AM")).toBeInTheDocument();
  });

  it("shows the blocking level when the target is capped", async () => {
    respond([setup({ capped_target: 2.15, available_reward_risk: 1.5, blocking_level: 2.15 })]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    expect(await screen.findByText("1.5R")).toBeInTheDocument();
    expect(screen.getByText("capped by level at 2.15")).toBeInTheDocument();
  });

  it("explains the score when expanded", async () => {
    respond([setup()]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Score details for HOST" }));

    const details = screen.getByText("Pattern quality").closest("dl") as HTMLElement;
    expect(within(details).getByText("Reward:risk")).toBeInTheDocument();
    expect(within(details).getByText("+40.0")).toBeInTheDocument();
  });

  it("lists bearish patterns as warnings when shorts are hidden", async () => {
    respond([setup()], [setup({ id: 3, ticker: "DOWN", direction: "short", pattern: "low_of_day_break", entry: 1.5 })]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    const warnings = await screen.findByRole("region", { name: "Bearish warnings" });
    expect(within(warnings).getByText("DOWN")).toBeInTheDocument();
    expect(within(warnings).getByText("Low-of-day break")).toBeInTheDocument();
  });

  it("marks setups whose stock also shows a bearish pattern", async () => {
    respond([setup({ has_conflict: true })]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    expect(await screen.findByText("Bearish pattern too")).toBeInTheDocument();
  });

  it("saves the show-short-setups setting and reloads", async () => {
    respond([setup()]);
    api.saveSettings.mockResolvedValue({ show_short_setups: true });
    render(<SetupsView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByLabelText("Show short setups"));

    await vi.waitFor(() => expect(api.fetchSetups).toHaveBeenCalledTimes(2));
    expect(api.saveSettings).toHaveBeenCalledWith({ show_short_setups: true });
  });

  it("shows scan failures after scanning", async () => {
    respond([]);
    api.runScan.mockResolvedValue({
      scanned: ["HOST"], failed: [{ ticker: "WORX", reason: "Finviz request failed (1m bars WORX): ReadTimeout" }],
      setups_found: 3, scanned_at: "2026-10-20T14:00:00Z",
    });
    render(<SetupsView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Scan watchlist" }));

    expect(await screen.findByText(/1 scanned, 1 failed/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("WORX: Finviz request failed");
  });

  it("explains the empty state", async () => {
    respond([]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    expect(await screen.findByText(/No setups detected in the last scan/)).toBeInTheDocument();
  });

  it("opens the stock view when a ticker is clicked", async () => {
    respond([setup()]);
    const onOpenStock = vi.fn();
    render(<SetupsView onOpenStock={onOpenStock} />);

    fireEvent.click(await screen.findByRole("link", { name: "HOST" }));

    expect(onOpenStock).toHaveBeenCalledWith("HOST");
  });

  it("shows each setup's stock verdict", async () => {
    respond([setup({ verdict: { call: "leans_long", score: 0.4, parts: {}, reasons: ["Above 5 of 5 trend lines"],
      computed_at: "2026-10-20T14:00:00Z" } })]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    const badge = await screen.findByText("Leans long");
    expect(badge.getAttribute("title")).toContain("Above 5 of 5 trend lines");
  });

  it("labels a short row's conflict as a bullish pattern", async () => {
    respond([setup({ direction: "short", pattern: "bear_flag", has_conflict: true })], [], true);
    render(<SetupsView onOpenStock={vi.fn()} />);

    expect(await screen.findByText("Bullish pattern too")).toBeInTheDocument();
  });

  it("shows the pattern's track record in the score details", async () => {
    respond([
      setup({ track_record: history({}) }),
      setup({ id: 2, ticker: "WORX", track_record: history({ trades: 12, has_enough_history: false }) }),
      setup({
        id: 3, ticker: "ONEDAY", track_record: history({ trades: 40, trading_days: 2, has_enough_history: false }),
      }),
    ]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Score details for HOST" }));
    expect(
      screen.getByText("Track record: 42 trades on 15 stocks over 9 days, 48% wins averaging +2.10R, +0.31R per trade"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Score details for WORX" }));
    expect(screen.getByText("Track record: not enough history yet (12 of 30 trades)")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Score details for ONEDAY" }));
    expect(
      screen.getByText("Track record: not enough history yet (40 trades, but from only 2 of 5 trading days)"),
    ).toBeInTheDocument();
  });

});
