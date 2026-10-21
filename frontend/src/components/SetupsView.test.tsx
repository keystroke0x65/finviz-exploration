import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Setup } from "../api/setups";
import { SetupsView } from "./SetupsView";

const api = { fetchSetups: vi.fn(), runScan: vi.fn(), saveSettings: vi.fn() };
vi.mock("../api/setups", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/setups")>()),
  fetchSetups: () => api.fetchSetups(),
  runScan: (ticker?: string) => api.runScan(ticker),
}));
vi.mock("../api/settings", () => ({ saveSettings: (settings: unknown) => api.saveSettings(settings) }));

function setup(overrides: Partial<Setup> = {}): Setup {
  return {
    id: 1, ticker: "HOST", pattern: "bull_flag", direction: "long", timeframe: "5m", entry: 2.0, stop: 1.9,
    capped_target: 2.3, target_3r: 2.3, available_reward_risk: 3.0, risk_percent: 5.0, blocking_level: null,
    partial_1r: 2.1, partial_2r: 2.2, trailing_stop: null, quality: 0.7, score: 81.5,
    score_parts: { reward_risk: 40, quality: 17.5, volume: 10, freshness: 10, timeframe_agreement: 0, conflict: 0 },
    key_points: [], state: "forming", session: "regular", detected_at: "2026-10-20T14:00:00Z",
    last_seen_at: "2026-10-20T14:00:30Z", has_conflict: false, ...overrides,
  };
}

function respond(setups: Setup[], warnings: Setup[] = [], showShorts = false) {
  api.fetchSetups.mockResolvedValue({ setups, warnings, show_short_setups: showShorts });
}

describe("SetupsView", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
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

    fireEvent.click(await screen.findByRole("button", { name: "HOST" }));

    expect(onOpenStock).toHaveBeenCalledWith("HOST");
  });

  it("shows each setup's stock verdict", async () => {
    respond([setup({ verdict: { call: "leans_long", score: 0.4, parts: {}, reasons: ["Above 5 of 5 trend lines"],
      computed_at: "2026-10-20T14:00:00Z" } })]);
    render(<SetupsView onOpenStock={vi.fn()} />);

    const badge = await screen.findByText("Leans long");
    expect(badge.getAttribute("title")).toContain("Above 5 of 5 trend lines");
  });
});
