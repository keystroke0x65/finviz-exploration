import { Fragment, useCallback, useEffect, useState } from "react";
import {
  fetchSetups,
  fetchScanStatus,
  MIN_TRADES_FOR_TRACK_RECORD,
  MIN_TRADING_DAYS_FOR_TRACK_RECORD,
  patternName,
  runScan,
  ScanResult,
  SCORE_PART_NAMES,
  Setup,
  ScanStatus,
  SetupsResponse,
  TrackRecordSummary,
} from "../api/setups";
import { saveSettings } from "../api/settings";
import { formatPrice } from "../format";
import { describeScanStatus } from "../scanStatus";
import { describeSetupState } from "../setupState";
import { VerdictBadge } from "./VerdictBadge";
import { StockLink } from "./StockLink";

interface SetupsViewProps {
  onOpenStock: (ticker: string) => void;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

function describeScan(result: ScanResult): string {
  return `${result.scanned.length} scanned, ${result.failed.length} failed, ${result.setups_found} setups found`;
}

function formatPoints(points: number): string {
  return `${points >= 0 ? "+" : ""}${points.toFixed(1)}`;
}

export function SetupsView({ onOpenStock }: SetupsViewProps) {
  const [response, setResponse] = useState<SetupsResponse | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const [setups, status] = await Promise.all([fetchSetups(), fetchScanStatus()]);
    setResponse(setups);
    setScanStatus(status);
  }, []);
  const scanNote = scanStatus ? describeScanStatus(scanStatus, new Date()) : null;

  useEffect(() => {
    reload().catch((loadError) => setError(errorMessage(loadError)));
  }, [reload]);

  async function handleScan() {
    setError(null);
    setIsScanning(true);
    try {
      setScanResult(await runScan());
      await reload();
    } catch (scanError) {
      setError(errorMessage(scanError));
    } finally {
      setIsScanning(false);
    }
  }

  async function handleToggleShorts(isShown: boolean) {
    setError(null);
    try {
      await saveSettings({ show_short_setups: isShown });
      await reload();
    } catch (saveError) {
      setError(errorMessage(saveError));
    }
  }

  return (
    <section>
      <div className="watchlist-toolbar">
        <p className="muted setups-intro">
          Patterns are detected by fixed rules from Finviz bars. They flag shapes worth checking on the
          chart; they don't predict.
        </p>
        <div className="toolbar">
          {scanResult && <span className="muted">{describeScan(scanResult)}</span>}
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={response?.show_short_setups ?? false}
              disabled={!response}
              onChange={(event) => handleToggleShorts(event.target.checked)}
            />
            Show short setups
          </label>
          <button type="button" className="button-primary" onClick={handleScan} disabled={isScanning}>
            {isScanning ? "Scanning… (up to 2 min)" : "Scan watchlist"}
          </button>
        </div>
      </div>

      {scanNote?.isProblem && (
        <p role="alert" className="alert">
          {scanNote.text}
        </p>
      )}
      {scanNote && !scanNote.isProblem && <p className="muted scan-status">{scanNote.text}</p>}
      {scanResult && scanResult.failed.length > 0 && (
        <div role="alert" className="alert">
          {scanResult.failed.map((failure) => (
            <p key={failure.ticker}>
              {failure.ticker}: {failure.reason}
            </p>
          ))}
        </div>
      )}
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      {response && response.setups.length === 0 && (
        <p className="empty-state">
          No setups detected in the last scan. Scans run every 15 minutes from 4:00 AM to 8:00 PM ET
          on active watchlist stocks, or scan now.
        </p>
      )}
      {response && response.setups.length > 0 && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Pattern</th>
                <th>Stock verdict</th>
                <th>Timeframe</th>
                <th>State</th>
                <th className="number">Entry</th>
                <th className="number">Stop</th>
                <th className="number">Target</th>
                <th className="number">Reward:risk</th>
                <th className="number">Risk</th>
                <th className="number">Score</th>
              </tr>
            </thead>
            <tbody>
              {response.setups.map((setup) => (
                <Fragment key={setup.id}>
                  <SetupRow
                    setup={setup}
                    showDirection={response.show_short_setups}
                    isExpanded={expandedId === setup.id}
                    onToggleScore={() => setExpandedId(expandedId === setup.id ? null : setup.id)}
                    onOpenStock={onOpenStock}
                  />
                  {expandedId === setup.id && (
                    <tr>
                      <td colSpan={11}>
                        <ScoreDetails setup={setup} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {response && response.warnings.length > 0 && (
        <section aria-labelledby="bearish-warnings" className="warnings">
          <h2 id="bearish-warnings" className="section-title">
            Bearish warnings
          </h2>
          <p className="muted">Stocks showing a bearish pattern. Short setups are hidden; turn them on above.</p>
          <ul className="warning-list">
            {response.warnings.map((warning) => (
              <li key={warning.id}>
                <StockLink ticker={warning.ticker} onOpen={onOpenStock} />
                <span>{patternName(warning.pattern)}</span>
                <span className="muted">
                  {warning.timeframe}, breaks down below {formatPrice(warning.entry)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}

interface SetupRowProps {
  setup: Setup;
  showDirection: boolean;
  isExpanded: boolean;
  onToggleScore: () => void;
  onOpenStock: (ticker: string) => void;
}

function SetupRow({ setup, showDirection, isExpanded, onToggleScore, onOpenStock }: SetupRowProps) {
  return (
    <tr>
      <td>
        <StockLink ticker={setup.ticker} onOpen={onOpenStock} />
        {setup.has_conflict && (
          <div>
            <span className="badge badge-warning">
              {setup.direction === "long" ? "Bearish pattern too" : "Bullish pattern too"}
            </span>
          </div>
        )}
      </td>
      <td>
        {patternName(setup.pattern)}
        {showDirection && <div className={setup.direction === "long" ? "gain" : "loss"}>{setup.direction}</div>}
      </td>
      <td>
        <VerdictBadge verdict={setup.verdict} />
      </td>
      <td>{setup.timeframe}</td>
      <td>{describeSetupState(setup)}</td>
      <td className="number">{formatPrice(setup.entry)}</td>
      <td className="number">{formatPrice(setup.stop)}</td>
      <td className="number">{formatPrice(setup.capped_target)}</td>
      <td className="number">
        {setup.available_reward_risk.toFixed(1)}R
        {setup.blocking_level != null && (
          <div className="muted">capped by level at {formatPrice(setup.blocking_level)}</div>
        )}
      </td>
      <td className="number">{setup.risk_percent.toFixed(1)}%</td>
      <td className="number">
        <button
          type="button"
          className="score-button"
          aria-expanded={isExpanded}
          aria-label={`Score details for ${setup.ticker}`}
          onClick={onToggleScore}
        >
          {setup.score.toFixed(0)}
        </button>
      </td>
    </tr>
  );
}

function formatSignedR(value: number | null): string {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}R`;
}

function describeTrackRecord(history: TrackRecordSummary | null | undefined): string {
  if (!history || history.trades < MIN_TRADES_FOR_TRACK_RECORD) {
    return `Track record: not enough history yet (${history?.trades ?? 0} of ${MIN_TRADES_FOR_TRACK_RECORD} trades)`;
  }
  if (!history.has_enough_history) {
    return (
      `Track record: not enough history yet (${history.trades} trades, but from only ` +
      `${history.trading_days} of ${MIN_TRADING_DAYS_FOR_TRACK_RECORD} trading days)`
    );
  }
  const winRate = history.win_rate == null ? "—" : `${Math.round(history.win_rate * 100)}%`;
  return (
    `Track record: ${history.trades} trades on ${history.tickers} stocks over ${history.trading_days} days, ` +
    `${winRate} wins averaging ${formatSignedR(history.average_win_r)}, ${formatSignedR(history.average_r)} per trade`
  );
}

function ScoreDetails({ setup }: { setup: Setup }) {
  return (
    <div className="score-details">
      <dl>
        {Object.entries(setup.score_parts).map(([part, points]) => (
          <div key={part}>
            <dt>{SCORE_PART_NAMES[part] ?? part}</dt>
            <dd className={points < 0 ? "loss" : undefined}>{formatPoints(points)}</dd>
          </div>
        ))}
      </dl>
      <p className="muted">{describeTrackRecord(setup.track_record)}</p>
      <p className="muted">
        Partial profits at {formatPrice(setup.partial_1r)} (1R) and {formatPrice(setup.partial_2r)} (2R)
        {setup.trailing_stop != null && <>; trail the stop under {formatPrice(setup.trailing_stop)}</>}.
        Full 3R target {formatPrice(setup.target_3r)}.
      </p>
    </div>
  );
}
