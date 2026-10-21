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
import { finvizQuoteUrl, formatEasternDate, formatPercent } from "../format";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

function summarizeFeederResult(result: FeederResult): string {
  return `${result.tickers_added.length} added, ${result.tickers_updated.length} updated, ${result.tickers_expired.length} expired`;
}

export function WatchlistView() {
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
      <h2>Watchlist</h2>
      <form onSubmit={handleAdd}>
        <label>
          Ticker
          <input type="text" value={tickerInput} onChange={(event) => setTickerInput(event.target.value)} />
        </label>
        <button type="submit">Add</button>
      </form>
      <button type="button" onClick={handleRefresh} disabled={isRefreshing}>
        Refresh from feeder
      </button>

      {feederStatus && (
        <p>
          Last feeder run: {new Date(feederStatus.finished_at).toLocaleString()} —{" "}
          {summarizeFeederResult(feederStatus)}
        </p>
      )}
      {feederStatus && feederStatus.failed_screens.length > 0 && (
        <div role="alert">
          {feederStatus.failed_screens.map((failure) => (
            <p key={failure.screen}>
              {failure.screen}: {failure.reason}
            </p>
          ))}
        </div>
      )}
      {error && <p role="alert">{error}</p>}

      {entries.length === 0 ? (
        <p>The watchlist is empty. Feeder screens add top gainers automatically.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Source</th>
              <th>Added</th>
              <th>Last seen</th>
              <th>Pinned</th>
              <th></th>
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
              />
            ))}
          </tbody>
        </table>
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
}

function WatchlistRow({ entry, isExpanded, onToggleHistory, onTogglePin, onRemove }: WatchlistRowProps) {
  return (
    <>
      <tr>
        <td>
          <a href={finvizQuoteUrl(entry.ticker)} target="_blank" rel="noreferrer">
            {entry.ticker}
          </a>
        </td>
        <td>{entry.source}</td>
        <td>{formatEasternDate(entry.added_at)}</td>
        <td>
          {entry.last_seen_in_feeder_at ? formatEasternDate(entry.last_seen_in_feeder_at) : "never"}
          {entry.expires_at && (
            <>
              {" "}
              <small>expires {formatEasternDate(entry.expires_at)}</small>
            </>
          )}
        </td>
        <td>
          <input
            type="checkbox"
            aria-label={`Pin ${entry.ticker}`}
            checked={entry.is_pinned}
            onChange={onTogglePin}
          />
        </td>
        <td>
          <button type="button" aria-label={`History for ${entry.ticker}`} onClick={onToggleHistory}>
            History ({entry.appearances.length})
          </button>{" "}
          <button type="button" onClick={onRemove}>
            Remove
          </button>
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={6}>
            {entry.appearances.length === 0 ? (
              "No feeder runs yet."
            ) : (
              <ul>
                {entry.appearances.map((appearance) => (
                  <li key={`${appearance.seen_on}-${appearance.screen_id}`}>
                    {appearance.seen_on}: {formatPercent(appearance.change_percent)}
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
