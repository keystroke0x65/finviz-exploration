import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WatchlistEntry } from "../api/watchlist";
import { WatchlistView } from "./WatchlistView";

const api = {
  listWatchlist: vi.fn(), addToWatchlist: vi.fn(), removeFromWatchlist: vi.fn(),
  setPinned: vi.fn(), refreshWatchlist: vi.fn(), fetchFeederStatus: vi.fn(),
};
vi.mock("../api/watchlist", () => ({
  listWatchlist: () => api.listWatchlist(),
  addToWatchlist: (ticker: string) => api.addToWatchlist(ticker),
  removeFromWatchlist: (ticker: string) => api.removeFromWatchlist(ticker),
  setPinned: (ticker: string, isPinned: boolean) => api.setPinned(ticker, isPinned),
  refreshWatchlist: () => api.refreshWatchlist(),
  fetchFeederStatus: () => api.fetchFeederStatus(),
}));

const AUTO_ENTRY: WatchlistEntry = {
  ticker: "HOST", source: "auto", added_at: "2026-10-03T14:00:00+00:00",
  last_seen_in_feeder_at: "2026-10-20T14:00:00+00:00", is_pinned: false,
  expires_at: "2027-01-18T14:00:00Z",
  snapshot: { price: 2.83, change_percent: 47.4, after_hours_change_percent: -3.53, relative_volume: 14.22,
    fetched_at: "2026-10-20T14:00:00Z" },
  verdict: { call: "no_clear_edge", score: 0.1, parts: {}, reasons: ["Volume balanced between up and down bars"],
    computed_at: "2026-10-20T14:00:00Z" },
  appearances: [
    { seen_on: "2026-10-20", change_percent: 47.4, screen_id: 1 },
    { seen_on: "2026-10-03", change_percent: 22.1, screen_id: 1 },
  ],
};
const MANUAL_ENTRY: WatchlistEntry = {
  ticker: "WORX", source: "manual", added_at: "2026-10-19T14:00:00+00:00",
  last_seen_in_feeder_at: null, is_pinned: false, expires_at: null, appearances: [], snapshot: null, verdict: null,
};

describe("WatchlistView", () => {
  beforeEach(() => {
    api.fetchFeederStatus.mockResolvedValue(null);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("lists entries with source and last seen", async () => {
    api.listWatchlist.mockResolvedValue([AUTO_ENTRY, MANUAL_ENTRY]);
    render(<WatchlistView onOpenStock={vi.fn()} />);

    const hostRow = await screen.findByRole("row", { name: /HOST/ });
    expect(within(hostRow).getByText("auto")).toBeInTheDocument();
    expect(within(hostRow).getByText("2026-10-20")).toBeInTheDocument();
    const worxRow = screen.getByRole("row", { name: /WORX/ });
    expect(within(worxRow).getByText("manual")).toBeInTheDocument();
    expect(within(worxRow).getByText("never")).toBeInTheDocument();
  });

  it("shows an expiry date for unpinned auto entries only", async () => {
    api.listWatchlist.mockResolvedValue([AUTO_ENTRY, MANUAL_ENTRY, { ...AUTO_ENTRY, ticker: "PIN", is_pinned: true, expires_at: null }]);
    render(<WatchlistView onOpenStock={vi.fn()} />);

    expect(within(await screen.findByRole("row", { name: /HOST/ })).getByText("expires 2027-01-18")).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /WORX/ })).queryByText(/expires/)).not.toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /PIN/ })).queryByText(/expires/)).not.toBeInTheDocument();
  });

  it("shows run history when a row is expanded", async () => {
    api.listWatchlist.mockResolvedValue([AUTO_ENTRY]);
    render(<WatchlistView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "History for HOST" }));

    expect(screen.getByText("+22.10%")).toBeInTheDocument();
  });

  it("toggles pin and re-renders the entry", async () => {
    api.listWatchlist.mockResolvedValue([AUTO_ENTRY]);
    api.setPinned.mockResolvedValue({ ...AUTO_ENTRY, is_pinned: true, expires_at: null });
    render(<WatchlistView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByRole("checkbox", { name: "Pin HOST" }));

    expect(api.setPinned).toHaveBeenCalledWith("HOST", true);
    expect(await screen.findByRole("checkbox", { name: "Pin HOST" })).toBeChecked();
    expect(screen.queryByText(/expires/)).not.toBeInTheDocument();
  });

  it("shows the backend error when adding an unknown ticker", async () => {
    api.listWatchlist.mockResolvedValue([]);
    api.addToWatchlist.mockRejectedValue(new Error("No Finviz data found for ticker 'ZZZZ'"));
    render(<WatchlistView onOpenStock={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText("Ticker"), { target: { value: "zzzz" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No Finviz data found for ticker 'ZZZZ'");
    expect(api.addToWatchlist).toHaveBeenCalledWith("ZZZZ");
  });

  it("shows failed feeder screens after refresh", async () => {
    api.listWatchlist.mockResolvedValue([]);
    api.refreshWatchlist.mockResolvedValue({
      screens_run: 2, tickers_added: ["HOST"], tickers_updated: [], tickers_expired: [],
      failed_screens: [{ screen: "After-hours", reason: "Finviz request failed (screen): ReadTimeout" }],
    });
    render(<WatchlistView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Refresh from feeder" }));

    expect(await screen.findByText(/^Last feeder run:/)).toHaveTextContent("1 added, 0 updated, 0 expired");
    expect(screen.getByRole("alert")).toHaveTextContent("After-hours: Finviz request failed (screen): ReadTimeout");
  });

  it("shows the last background feeder run and its failures on load", async () => {
    api.listWatchlist.mockResolvedValue([]);
    api.fetchFeederStatus.mockResolvedValue({
      finished_at: "2026-10-20T14:00:00Z", screens_run: 1, tickers_added: [], tickers_updated: [],
      tickers_expired: [],
      failed_screens: [{ screen: "Top gainers — low float", reason: "Finviz Elite API rejected the configured auth token." }],
    });
    render(<WatchlistView onOpenStock={vi.fn()} />);

    expect(await screen.findByText(/^Last feeder run:/)).toHaveTextContent("0 added, 0 updated, 0 expired");
    expect(screen.getByRole("alert")).toHaveTextContent("Top gainers — low float: Finviz Elite API rejected");
  });

  it("summarises which of the last 30 days a stock ran", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-20T18:00:00Z"));
    api.listWatchlist.mockResolvedValue([AUTO_ENTRY]);
    render(<WatchlistView onOpenStock={vi.fn()} />);

    // Oct 20 and Oct 3 are both within the 30 days ending Oct 20.
    expect(await screen.findByRole("img", { name: "Ran on 2 of the last 30 days" })).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("shows price and change from the latest snapshot", async () => {
    api.listWatchlist.mockResolvedValue([AUTO_ENTRY, MANUAL_ENTRY]);
    render(<WatchlistView onOpenStock={vi.fn()} />);

    const hostRow = await screen.findByRole("row", { name: /HOST/ });
    expect(within(hostRow).getByText("2.83")).toBeInTheDocument();
    expect(within(hostRow).getByText("+47.40%")).toBeInTheDocument();
    expect(within(hostRow).getByText("-3.53%")).toBeInTheDocument();
  });

  it("opens the stock view from a ticker", async () => {
    api.listWatchlist.mockResolvedValue([AUTO_ENTRY]);
    const onOpenStock = vi.fn();
    render(<WatchlistView onOpenStock={onOpenStock} />);

    fireEvent.click(await screen.findByRole("button", { name: "HOST" }));

    expect(onOpenStock).toHaveBeenCalledWith("HOST");
  });

  it("shows verdicts on the watchlist", async () => {
    api.listWatchlist.mockResolvedValue([AUTO_ENTRY, MANUAL_ENTRY]);
    render(<WatchlistView onOpenStock={vi.fn()} />);

    const hostRow = await screen.findByRole("row", { name: /HOST/ });
    expect(within(hostRow).getByText("No clear edge")).toBeInTheDocument();
  });
});
