import { useState } from "react";
import type { ScreenRow, ScreenRun } from "../api/screens";
import {
  changeClass,
  finvizQuoteUrl,
  formatCount,
  formatNumber,
  formatSignedPercent,
  isWebUrl,
  MISSING_VALUE,
} from "../format";

interface ScreenResultsTableProps {
  run: ScreenRun;
  onAddToWatchlist: (ticker: string) => void;
  watchlistTickers: Set<string>;
  onOpenStock: (ticker: string) => void;
}

type SortableColumn = keyof Pick<
  ScreenRow,
  | "ticker"
  | "price"
  | "change_percent"
  | "after_hours_change_percent"
  | "volume"
  | "relative_volume"
  | "float_millions"
  | "market_cap_millions"
>;

interface Column {
  key: SortableColumn;
  label: string;
  isNumeric: boolean;
}

const COLUMNS: Column[] = [
  { key: "ticker", label: "Ticker", isNumeric: false },
  { key: "price", label: "Price", isNumeric: true },
  { key: "change_percent", label: "Change", isNumeric: true },
  { key: "after_hours_change_percent", label: "After-hours", isNumeric: true },
  { key: "volume", label: "Volume", isNumeric: true },
  { key: "relative_volume", label: "Rel vol", isNumeric: true },
  { key: "float_millions", label: "Float (M)", isNumeric: true },
  { key: "market_cap_millions", label: "Mkt cap (M)", isNumeric: true },
];

interface SortState {
  column: SortableColumn;
  isDescending: boolean;
}

function compareRows(left: ScreenRow, right: ScreenRow, sort: SortState): number {
  const leftValue = left[sort.column];
  const rightValue = right[sort.column];
  // Missing values always sink to the bottom, whichever direction is chosen.
  if (leftValue == null) return rightValue == null ? 0 : 1;
  if (rightValue == null) return -1;
  const order = leftValue < rightValue ? -1 : leftValue > rightValue ? 1 : 0;
  return sort.isDescending ? -order : order;
}

export function ScreenResultsTable({ run, onAddToWatchlist, watchlistTickers, onOpenStock }: ScreenResultsTableProps) {
  // Null keeps Finviz's own order (the screen's sort setting).
  const [sort, setSort] = useState<SortState | null>(null);

  function handleSort(column: Column) {
    const isSameColumn = sort?.column === column.key;
    // Numbers start high-to-low (biggest movers first); tickers start A-Z.
    setSort({ column: column.key, isDescending: isSameColumn ? !sort.isDescending : column.isNumeric });
  }

  if (run.rows.length === 0) {
    return (
      <p className="empty-state">
        No stocks match this screen right now. Top-gainer screens fill up once pre-market opens at
        4:00 AM ET.
      </p>
    );
  }

  const rows = sort ? [...run.rows].sort((left, right) => compareRows(left, right, sort)) : run.rows;

  return (
    <>
      <p className="fetched-at">Fetched {new Date(run.fetched_at).toLocaleTimeString()}</p>
      <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th key={column.key} className={column.isNumeric ? "number" : undefined}>
                <button
                  type="button"
                  className="sort-button"
                  data-active={sort?.column === column.key}
                  aria-label={`Sort by ${column.label}`}
                  onClick={() => handleSort(column)}
                >
                  {column.label}
                  {sort?.column === column.key && (sort.isDescending ? " ▼" : " ▲")}
                </button>
              </th>
            ))}
            <th>Latest news</th>
            <th>
              <span className="visually-hidden">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.ticker}>
              <td>
                <button type="button" className="ticker-button" onClick={() => onOpenStock(row.ticker)}>
                  {row.ticker}
                </button>{" "}
                <a
                  className="small-link"
                  href={finvizQuoteUrl(row.ticker)}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`Open ${row.ticker} on Finviz`}
                >
                  Finviz
                </a>
                <div className="company muted" title={row.company ?? undefined}>
                  {row.company ?? MISSING_VALUE}
                </div>
              </td>
              <td className="number">{formatNumber(row.price)}</td>
              <td className={`number ${changeClass(row.change_percent)}`}>
                {formatSignedPercent(row.change_percent)}
              </td>
              <td className={`number ${changeClass(row.after_hours_change_percent)}`}>
                {formatSignedPercent(row.after_hours_change_percent)}
              </td>
              <td className="number">{formatCount(row.volume)}</td>
              <td className="number">{formatNumber(row.relative_volume)}</td>
              <td className="number">{formatNumber(row.float_millions)}</td>
              <td className="number">{formatNumber(row.market_cap_millions)}</td>
              <td>
                {row.news_title && isWebUrl(row.news_url) ? (
                  <a className="headline" href={row.news_url} target="_blank" rel="noreferrer" title={row.news_title}>
                    {row.news_title}
                  </a>
                ) : (
                  <span className="headline">{row.news_title ?? MISSING_VALUE}</span>
                )}
              </td>
              <td>
                <div className="row-actions">
                  {watchlistTickers.has(row.ticker) ? (
                    <button type="button" disabled aria-label={`${row.ticker} is on the watchlist`}>
                      On watchlist
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onAddToWatchlist(row.ticker)}
                      aria-label={`Add ${row.ticker} to watchlist`}
                    >
                      + Watchlist
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </>
  );
}
