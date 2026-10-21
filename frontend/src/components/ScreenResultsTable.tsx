import type { ScreenRun } from "../api/screens";
import {
  finvizQuoteUrl,
  formatCount,
  formatNumber,
  formatPercent,
  isWebUrl,
  MISSING_VALUE,
} from "../format";

interface ScreenResultsTableProps {
  run: ScreenRun;
  onAddToWatchlist: (ticker: string) => void;
}

const COLUMN_HEADINGS = [
  "Ticker", "Company", "Price", "Change", "AH Change", "Volume", "Rel Vol",
  "Float (M)", "Mkt Cap (M)", "News", "",
];

export function ScreenResultsTable({ run, onAddToWatchlist }: ScreenResultsTableProps) {
  return (
    <section>
      <p>Fetched {new Date(run.fetched_at).toLocaleString()}</p>
      {run.is_possibly_unfiltered && (
        <p role="alert">
          Finviz may have ignored some filters — check the screen's codes. Finviz returns the
          whole market instead of an error when it doesn't recognise a code.
        </p>
      )}
      {run.rows.length === 0 ? (
        <p>No stocks match this screen right now.</p>
      ) : (
        <table>
          <thead>
            <tr>
              {COLUMN_HEADINGS.map((heading) => (
                <th key={heading}>{heading}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {run.rows.map((row) => (
              <tr key={row.ticker}>
                <td>{row.ticker}</td>
                <td>{row.company ?? MISSING_VALUE}</td>
                <td>{formatNumber(row.price)}</td>
                <td>{formatPercent(row.change_percent)}</td>
                <td>{formatPercent(row.after_hours_change_percent)}</td>
                <td>{formatCount(row.volume)}</td>
                <td>{formatNumber(row.relative_volume)}</td>
                <td>{formatNumber(row.float_millions)}</td>
                <td>{formatNumber(row.market_cap_millions)}</td>
                <td>
                  {row.news_title && isWebUrl(row.news_url) ? (
                    <a href={row.news_url} target="_blank" rel="noreferrer">
                      {row.news_title}
                    </a>
                  ) : (
                    (row.news_title ?? MISSING_VALUE)
                  )}
                </td>
                <td>
                  <a
                    href={finvizQuoteUrl(row.ticker)}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`Open ${row.ticker} on Finviz`}
                  >
                    Finviz
                  </a>{" "}
                  <button
                    type="button"
                    onClick={() => onAddToWatchlist(row.ticker)}
                    aria-label={`Add ${row.ticker} to watchlist`}
                  >
                    + Watchlist
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
