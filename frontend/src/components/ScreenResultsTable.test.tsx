import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ScreenRow, ScreenRun } from "../api/screens";
import { ScreenResultsTable } from "./ScreenResultsTable";

const HOST: ScreenRow = {
  ticker: "HOST", company: "Host Digital Inc", country: "USA", market_cap_millions: 79.8,
  float_millions: 5.46, average_volume_thousands: 433.04, relative_volume: 14.22, price: 2.83,
  change_percent: 47.4, volume: 6158186, after_hours_close: 2.73,
  after_hours_change_percent: -3.53, news_time: "2026-10-20T10:36:03-04:00",
  news_url: "https://elite.finviz.com/news/1", news_title: "Buyback",
};

function run(overrides: Partial<ScreenRun> = {}): ScreenRun {
  return { rows: [HOST], fetched_at: "2026-10-20T14:00:00Z", ...overrides };
}

describe("ScreenResultsTable", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a row with formatted numbers and a news link", () => {
    render(<ScreenResultsTable run={run()} onAddToWatchlist={vi.fn()} watchlistTickers={new Set()} onOpenStock={vi.fn()} />);

    const row = screen.getByRole("row", { name: /HOST/ });
    expect(within(row).getByText("+47.40%")).toBeInTheDocument();
    expect(within(row).getByText("-3.53%")).toBeInTheDocument();
    expect(within(row).getByText("6,158,186")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "Buyback" })).toHaveAttribute(
      "href", "https://elite.finviz.com/news/1",
    );
    expect(within(row).getByRole("link", { name: "Open HOST on Finviz" })).toHaveAttribute(
      "href", "https://finviz.com/quote.ashx?t=HOST",
    );
  });

  it("shows when the latest news came out, before the headline", () => {
    render(<ScreenResultsTable run={run()} onAddToWatchlist={vi.fn()} watchlistTickers={new Set()} onOpenStock={vi.fn()} />);

    const row = screen.getByRole("row", { name: /HOST/ });
    expect(within(row).getByText(/^Oct 20, (2026, )?10:36 AM$/)).toBeInTheDocument();
  });

  it("leaves out the news time when Finviz didn't give one", () => {
    render(
      <ScreenResultsTable
        run={run({ rows: [{ ...HOST, news_time: null }] })}
        onAddToWatchlist={vi.fn()}
        watchlistTickers={new Set()}
        onOpenStock={vi.fn()}
      />,
    );

    const row = screen.getByRole("row", { name: /HOST/ });
    expect(within(row).queryByText(/10:36 AM/)).not.toBeInTheDocument();
    expect(within(row).getByText("Buyback")).toBeInTheDocument();
  });

  it("shows an empty-state message when no rows", () => {
    render(<ScreenResultsTable run={run({ rows: [] })} onAddToWatchlist={vi.fn()} watchlistTickers={new Set()} onOpenStock={vi.fn()} />);

    expect(screen.getByText(/^No stocks match this screen right now\./)).toBeInTheDocument();
  });

  it("renders missing numbers as a dash", () => {
    const sparse: ScreenRow = { ...HOST, ticker: "NOAH", after_hours_change_percent: null,
      relative_volume: null, news_title: null, news_url: null };

    render(<ScreenResultsTable run={run({ rows: [sparse] })} onAddToWatchlist={vi.fn()} watchlistTickers={new Set()} onOpenStock={vi.fn()} />);

    const row = screen.getByRole("row", { name: /NOAH/ });
    expect(within(row).getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("does not link news whose url isn't http(s)", () => {
    const hostile: ScreenRow = { ...HOST, news_url: "javascript:alert(1)" };

    render(<ScreenResultsTable run={run({ rows: [hostile] })} onAddToWatchlist={vi.fn()} watchlistTickers={new Set()} onOpenStock={vi.fn()} />);

    expect(screen.queryByRole("link", { name: "Buyback" })).not.toBeInTheDocument();
    expect(screen.getByText("Buyback")).toBeInTheDocument();
  });

  it("shows when the data was fetched", () => {
    render(<ScreenResultsTable run={run()} onAddToWatchlist={vi.fn()} watchlistTickers={new Set()} onOpenStock={vi.fn()} />);

    expect(screen.getByText(/^Fetched /)).toBeInTheDocument();
  });

  it("calls onAddToWatchlist with the row ticker", () => {
    const onAddToWatchlist = vi.fn();
    render(<ScreenResultsTable run={run()} onAddToWatchlist={onAddToWatchlist} watchlistTickers={new Set()} onOpenStock={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Add HOST to watchlist" }));

    expect(onAddToWatchlist).toHaveBeenCalledWith("HOST");
  });

  it("sorts rows by a column when its header is clicked", () => {
    const small: ScreenRow = { ...HOST, ticker: "WORX", change_percent: 12.5 };
    render(<ScreenResultsTable run={run({ rows: [small, HOST] })} onAddToWatchlist={vi.fn()} watchlistTickers={new Set()} onOpenStock={vi.fn()} />);
    const tickersInOrder = () =>
      screen.getAllByRole("row").slice(1).map((row) => within(row).getAllByRole("button")[0].textContent);

    fireEvent.click(screen.getByRole("button", { name: "Sort by Change" }));
    expect(tickersInOrder()).toEqual(["HOST", "WORX"]);

    fireEvent.click(screen.getByRole("button", { name: "Sort by Change" }));
    expect(tickersInOrder()).toEqual(["WORX", "HOST"]);
  });

  it("shows tickers already on the watchlist as added", () => {
    render(<ScreenResultsTable run={run()} onAddToWatchlist={vi.fn()} watchlistTickers={new Set(["HOST"])} onOpenStock={vi.fn()} />);

    expect(screen.getByRole("button", { name: "HOST is on the watchlist" })).toBeDisabled();
  });
});
