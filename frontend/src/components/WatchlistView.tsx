import { FormEvent, useEffect, useState } from "react";
import {
  addToWatchlist,
  FeederResult,
  FeederStatus,
  fetchFeederStatus,
  listWatchlist,
  refreshWatchlist,
  removeFromWatchlist,
  setPinned,
  WatchlistEntry,
} from "../api/watchlist";
import {
  changeClass,
  finvizQuoteUrl,
  formatEasternDate,
  formatNumber,
  formatPrice,
  formatSignedPercent,
  MISSING_VALUE,
} from "../format";
import { RunDots } from "./RunDots";
import { VerdictBadge } from "./VerdictBadge";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

function summarizeFeederResult(result: FeederResult): string {
  return `${result.tickers_added.length} added, ${result.tickers_updated.length} updated, ${result.tickers_expired.length} expired`;
}

interface WatchlistViewProps {
  onOpenStock: (ticker: string) => void;
}

export function WatchlistView({ onOpenStock }: WatchlistViewProps) {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [tickerInput, setTickerInput] = useState("");
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [feederStatus, setFeederStatus] = useState<FeederStatus | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reloadEntries() {
    setEntries(await listWatchlist());
  }

  useEffect(() => {
    // The background feeder runs every 15 minutes; showing its last outcome is
    // the only way its failures (e.g. an expired token) become visible.
    Promise.all([reloadEntries(), fetchFeederStatus().then(setFeederStatus)]).catch((loadError) =>
      setError(errorMessage(loadError)),
    );
  }, []);

  async function runAction(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
    } catch (actionError) {
      setError(errorMessage(actionError));
    }
  }

  function handleAdd(event: FormEvent) {
    event.preventDefault();
    const ticker = tickerInput.trim().toUpperCase();
    if (!ticker) {
      return;
    }
    runAction(async () => {
      await addToWatchlist(ticker);
      setTickerInput("");
      await reloadEntries();
    });
  }

  function handleTogglePin(entry: WatchlistEntry) {
    runAction(async () => {
      const updated = await setPinned(entry.ticker, !entry.is_pinned);
      setEntries((current) => current.map((existing) => (existing.ticker === updated.ticker ? updated : existing)));
    });
  }

  function handleRemove(entry: WatchlistEntry) {
    if (!window.confirm(`Remove ${entry.ticker} from the watchlist?`)) {
      return;
    }
    runAction(async () => {
      await removeFromWatchlist(entry.ticker);
      await reloadEntries();
    });
  }

  function handleRefresh() {
    setIsRefreshing(true);
    runAction(async () => {
      const result = await refreshWatchlist();
      setFeederStatus({ ...result, finished_at: new Date().toISOString() });
      await reloadEntries();
    }).finally(() => setIsRefreshing(false));
  }

  return (
    <section>
      <div className="watchlist-toolbar">
        <form className="add-form" onSubmit={handleAdd}>
          <label className="field">
            Ticker
            <input
              type="text"
              value={tickerInput}
              onChange={(event) => setTickerInput(event.target.value)}
              placeholder="e.g. HOST"
            />
          </label>
          <button type="submit" disabled={!tickerInput.trim()}>
            Add
          </button>
        </form>
        <div className="toolbar">
          {feederStatus && (
            <span className="muted">
              Last feeder run: {new Date(feederStatus.finished_at).toLocaleString()} —{" "}
              {summarizeFeederResult(feederStatus)}
            </span>
          )}
          <button type="button" className="button-primary" onClick={handleRefresh} disabled={isRefreshing}>
            {isRefreshing ? "Refreshing…" : "Refresh from feeder"}
          </button>
        </div>
      </div>

      {feederStatus && feederStatus.failed_screens.length > 0 && (
        <div role="alert" className="alert">
          {feederStatus.failed_screens.map((failure) => (
            <p key={failure.screen}>
              {failure.screen}: {failure.reason}
            </p>
          ))}
        </div>
      )}
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      {entries.length === 0 ? (
        <p className="empty-state">
          The watchlist is empty. Screens marked "feeds watchlist" add their stocks here every 15
          minutes from 4:00 AM to 8:00 PM ET, or add a ticker above.
        </p>
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th className="number">Price</th>
                <th className="number">Change</th>
                <th className="number">After-hours</th>
                <th className="number">Rel vol</th>
                <th>Verdict</th>
                <th>Source</th>
                <th>Last 30 days</th>
                <th>Last seen</th>
                <th>Added</th>
                <th>Pin</th>
                <th>
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <WatchlistRow
                  key={entry.ticker}
                  entry={entry}
                  isExpanded={expandedTicker === entry.ticker}
                  onToggleHistory={() => setExpandedTicker(expandedTicker === entry.ticker ? null : entry.ticker)}
                  onTogglePin={() => handleTogglePin(entry)}
                  onRemove={() => handleRemove(entry)}
                  onOpenStock={onOpenStock}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

interface WatchlistRowProps {
  entry: WatchlistEntry;
  isExpanded: boolean;
  onToggleHistory: () => void;
  onTogglePin: () => void;
  onRemove: () => void;
  onOpenStock: (ticker: string) => void;
}

function WatchlistRow({ entry, isExpanded, onToggleHistory, onTogglePin, onRemove, onOpenStock }: WatchlistRowProps) {
  const snapshot = entry.snapshot;
  return (
    <>
      <tr>
        <td>
          <button type="button" className="ticker-button" onClick={() => onOpenStock(entry.ticker)}>
            {entry.ticker}
          </button>{" "}
          <a
            className="small-link"
            href={finvizQuoteUrl(entry.ticker)}
            target="_blank"
            rel="noreferrer"
            aria-label={`Open ${entry.ticker} on Finviz`}
          >
            Finviz
          </a>
        </td>
        <td className="number" title={snapshot ? `as of ${new Date(snapshot.fetched_at).toLocaleTimeString()}` : undefined}>
          {snapshot ? formatPrice(snapshot.price) : MISSING_VALUE}
        </td>
        <td className={`number ${changeClass(snapshot?.change_percent ?? null)}`}>
          {formatSignedPercent(snapshot?.change_percent ?? null)}
        </td>
        <td className={`number ${changeClass(snapshot?.after_hours_change_percent ?? null)}`}>
          {formatSignedPercent(snapshot?.after_hours_change_percent ?? null)}
        </td>
        <td className="number">{formatNumber(snapshot?.relative_volume ?? null)}</td>
        <td>
          <VerdictBadge verdict={entry.verdict} />
        </td>
        <td>
          <span className="badge" data-source={entry.source}>
            {entry.source}
          </span>
        </td>
        <td>
          <RunDots appearances={entry.appearances} />
        </td>
        <td>
          {entry.last_seen_in_feeder_at ? formatEasternDate(entry.last_seen_in_feeder_at) : "never"}
          {entry.expires_at && (
            <>
              {" "}
              <small className="muted">expires {formatEasternDate(entry.expires_at)}</small>
            </>
          )}
        </td>
        <td>{formatEasternDate(entry.added_at)}</td>
        <td>
          <input
            type="checkbox"
            aria-label={`Pin ${entry.ticker}`}
            checked={entry.is_pinned}
            onChange={onTogglePin}
          />
        </td>
        <td>
          <div className="row-actions">
            <button
              type="button"
              className="button-quiet"
              aria-label={`History for ${entry.ticker}`}
              aria-expanded={isExpanded}
              onClick={onToggleHistory}
            >
              History ({entry.appearances.length})
            </button>
            <button type="button" className="button-quiet" onClick={onRemove}>
              Remove
            </button>
          </div>
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={12}>
            {entry.appearances.length === 0 ? (
              <span className="muted">No feeder runs yet.</span>
            ) : (
              <ul className="history-list">
                {entry.appearances.map((appearance) => (
                  <li key={`${appearance.seen_on}-${appearance.screen_id}`}>
                    {appearance.seen_on}:{" "}
                    <span className={changeClass(appearance.change_percent)}>
                      {formatSignedPercent(appearance.change_percent)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
