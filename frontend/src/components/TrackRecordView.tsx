import { useEffect, useState } from "react";
import {
  MIN_TRADES_FOR_TRACK_RECORD,
  MIN_TRADING_DAYS_FOR_TRACK_RECORD,
  patternName,
  Timeframe,
} from "../api/setups";
import {
  fetchTrackRecord,
  FloatBucket,
  SessionName,
  TrackRecordFilters,
  TrackRecordResponse,
} from "../api/trackRecord";
import { MISSING_VALUE } from "../format";

const FLOAT_LABELS: Record<FloatBucket, string> = {
  under_5m: "Under 5M",
  "5m_to_10m": "5M–10M",
  "10m_to_20m": "10M–20M",
  "20m_to_50m": "20M–50M",
  over_50m: "Over 50M",
  unknown: "Unknown",
};
const SESSION_LABELS: Record<SessionName, string> = {
  "pre-market": "Pre-market",
  regular: "Regular hours",
  "after-hours": "After-hours",
  daily: "Daily bars",
};
const TIMEFRAMES: Timeframe[] = ["1m", "5m", "daily"];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

function formatR(value: number | null, isSigned = false): string {
  if (value == null) return MISSING_VALUE;
  const sign = isSigned && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}R`;
}

function dateSpan(firstDay: string | null, lastDay: string | null): string | undefined {
  if (!firstDay || !lastDay) return undefined;
  return firstDay === lastDay ? firstDay : `${firstDay} to ${lastDay}`;
}

export function TrackRecordView() {
  const [filters, setFilters] = useState<TrackRecordFilters>({ timeframe: null, float_bucket: null, session: null });
  const [response, setResponse] = useState<TrackRecordResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;
    setError(null);
    fetchTrackRecord(filters)
      .then((loaded) => {
        if (isCurrent) setResponse(loaded);
      })
      .catch((loadError) => {
        if (isCurrent) setError(errorMessage(loadError));
      });
    return () => {
      isCurrent = false;
    };
  }, [filters]);

  function setFilter<K extends keyof TrackRecordFilters>(name: K, value: string) {
    setFilters({ ...filters, [name]: value || null });
  }

  return (
    <section>
      <div className="watchlist-toolbar">
        <p className="muted setups-intro">
          How each pattern has actually played out on your stocks. Only trades you could have taken count: a
          setup counts once price reached its entry, then it scores its reward:risk if it hit the target, −1R if
          it hit the stop, 0R if it expired. A pattern's history starts to move its setups' scores once it has{" "}
          {response?.min_trades ?? MIN_TRADES_FOR_TRACK_RECORD} trades from at least{" "}
          {response?.min_trading_days ?? MIN_TRADING_DAYS_FOR_TRACK_RECORD} different trading days.
        </p>
        <div className="toolbar">
          <label className="field">
            Timeframe
            <select value={filters.timeframe ?? ""} onChange={(event) => setFilter("timeframe", event.target.value)}>
              <option value="">All</option>
              {TIMEFRAMES.map((timeframe) => (
                <option key={timeframe} value={timeframe}>
                  {timeframe}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Float
            <select
              value={filters.float_bucket ?? ""}
              onChange={(event) => setFilter("float_bucket", event.target.value)}
            >
              <option value="">All</option>
              {Object.entries(FLOAT_LABELS).map(([bucket, label]) => (
                <option key={bucket} value={bucket}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Session
            <select value={filters.session ?? ""} onChange={(event) => setFilter("session", event.target.value)}>
              <option value="">All</option>
              {Object.entries(SESSION_LABELS).map(([session, label]) => (
                <option key={session} value={session}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {response && response.rows.length === 0 && (
        <p className="empty-state">
          No resolved setups yet for these filters. Outcomes are filled in as setups resolve: intraday setups by
          8:00 PM ET the same day, daily setups after 20 sessions.
        </p>
      )}
      {response && response.rows.length > 0 && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Pattern</th>
                <th>Timeframe</th>
                <th className="number">Trades</th>
                <th className="number">Win rate</th>
                <th className="number">Average R</th>
                <th className="number">Average win</th>
                <th className="number">Average best move</th>
                <th className="number">Stocks</th>
                <th className="number">Days</th>
                <th className="number">Not trades</th>
                <th className="number">Open</th>
              </tr>
            </thead>
            <tbody>
              {response.rows.map((row) => {
                const isThin = !row.has_enough_history;
                return (
                  <tr key={`${row.pattern}-${row.timeframe}`} data-thin={isThin}>
                    <td>
                      {patternName(row.pattern)}
                      {isThin && <div className="muted">not enough history yet</div>}
                    </td>
                    <td>{row.timeframe}</td>
                    <td className="number">{row.trades}</td>
                    <td className="number">{row.win_rate == null ? MISSING_VALUE : `${Math.round(row.win_rate * 100)}%`}</td>
                    <td className={`number ${row.average_r != null && row.average_r < 0 ? "loss" : "gain"}`}>
                      {formatR(row.average_r, true)}
                    </td>
                    <td className="number">{formatR(row.average_win_r, true)}</td>
                    <td className="number">{formatR(row.average_max_favorable_r)}</td>
                    <td className="number">{row.tickers}</td>
                    <td className="number" title={dateSpan(row.first_day, row.last_day)}>
                      {row.trading_days}
                    </td>
                    <td className="number">{row.not_trades}</td>
                    <td className="number">{row.still_open}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
