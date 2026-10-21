import { useEffect, useMemo, useState } from "react";
import { BarsResponse, fetchBars } from "../api/bars";
import {
  fetchStockSetups,
  fetchStockVerdict,
  patternName,
  runScan,
  Setup,
  SetupsResponse,
  Timeframe,
  Verdict,
} from "../api/setups";
import { fetchQuote, Quote } from "../api/stocks";
import { finvizQuoteUrl, formatPrice } from "../format";
import { CandleChart, ChartLevel } from "./CandleChart";
import { QuoteTable } from "./QuoteTable";
import { StockSearch } from "./StockSearch";
import { VerdictBadge } from "./VerdictBadge";

interface StockViewProps {
  ticker: string | null;
  onTickerChange: (ticker: string) => void;
}

const TIMEFRAMES: Timeframe[] = ["1m", "5m", "daily"];
// Initial zoom: about the last 3 hours (1m), one full 4 AM-8 PM day (5m), six months (daily).
const VISIBLE_BARS: Record<Timeframe, number> = { "1m": 180, "5m": 192, daily: 126 };
// Daily levels far from the current price only clutter the chart.
const LEVEL_RANGE_FRACTION = 0.3;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

function nearbyDailyLevels(bars: BarsResponse): ChartLevel[] {
  const lastClose = bars.bars[bars.bars.length - 1]?.close;
  if (lastClose == null) {
    return [];
  }
  return bars.daily_levels
    .filter((level) => Math.abs(level.price - lastClose) / lastClose <= LEVEL_RANGE_FRACTION)
    .map((level) => ({ price: level.price, label: `Level (${level.touches}×)`, kind: "level" }));
}

function sessionLevels(bars: BarsResponse): ChartLevel[] {
  const session = bars.session;
  if (!session) {
    return [];
  }
  const candidates: [number | null, string][] = [
    [session.premarket_high, "PM high"],
    [session.premarket_low, "PM low"],
    [session.previous_close, "Prev close"],
  ];
  return candidates.flatMap(([price, label]) => (price == null ? [] : [{ price, label, kind: "session" as const }]));
}

function setupLevels(setup: Setup, isWarningOnly: boolean): ChartLevel[] {
  // Never draw a short trade plan while short setups are switched off.
  if (isWarningOnly) {
    return [{ price: setup.entry, label: "Breakdown", kind: "session" }];
  }
  return [
    { price: setup.entry, label: "Entry", kind: "entry" },
    { price: setup.stop, label: "Stop", kind: "stop" },
    { price: setup.capped_target, label: setup.blocking_level != null ? "Target (capped)" : "Target 3R", kind: "target" },
  ];
}

export function StockView({ ticker, onTickerChange }: StockViewProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>("5m");
  const [bars, setBars] = useState<BarsResponse | null>(null);
  const [setups, setSetups] = useState<SetupsResponse | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [selectedSetupId, setSelectedSetupId] = useState<number | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) {
      return;
    }
    setSelectedSetupId(null);
    setQuote(null);
    setVerdict(null);
    Promise.all([
      fetchStockSetups(ticker).then(setSetups),
      fetchQuote(ticker).then(setQuote),
      fetchStockVerdict(ticker).then(setVerdict),
    ]).catch((loadError) => setError(errorMessage(loadError)));
  }, [ticker]);

  useEffect(() => {
    if (!ticker) {
      return;
    }
    setError(null);
    setBars(null);
    fetchBars(ticker, timeframe)
      .then(setBars)
      .catch((loadError) => setError(errorMessage(loadError)));
  }, [ticker, timeframe]);

  const allSetups = useMemo(() => [...(setups?.setups ?? []), ...(setups?.warnings ?? [])], [setups]);
  const selectedSetup = allSetups.find((setup) => setup.id === selectedSetupId) ?? null;

  const chartLevels = useMemo(() => {
    if (!bars) {
      return [];
    }
    const isWarningOnly = selectedSetup?.direction === "short" && !setups?.show_short_setups;
    const selectedLevels = selectedSetup ? setupLevels(selectedSetup, isWarningOnly) : [];
    return [...nearbyDailyLevels(bars), ...sessionLevels(bars), ...selectedLevels];
  }, [bars, selectedSetup, setups]);

  const outline = selectedSetup && selectedSetup.timeframe === timeframe ? selectedSetup.key_points : null;

  async function handleScan() {
    if (!ticker) {
      return;
    }
    setIsScanning(true);
    setError(null);
    try {
      await runScan(ticker);
      setSetups(await fetchStockSetups(ticker));
      setVerdict(await fetchStockVerdict(ticker));
    } catch (scanError) {
      setError(errorMessage(scanError));
    } finally {
      setIsScanning(false);
    }
  }

  function handleSelectSetup(setup: Setup) {
    setSelectedSetupId(setup.id);
    setTimeframe(setup.timeframe);
  }

  return (
    <section className="stock-view">
      <div className="stock-header">
        <div className="lookup">
          <StockSearch onSearch={onTickerChange} />
        </div>
        {ticker && (
          <div className="toolbar">
            <h2 className="results-title">{ticker}</h2>
            <a href={finvizQuoteUrl(ticker)} target="_blank" rel="noreferrer" aria-label={`Open ${ticker} on Finviz`}>
              Finviz
            </a>
            <button type="button" onClick={handleScan} disabled={isScanning}>
              {isScanning ? "Scanning…" : "Scan this stock"}
            </button>
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!ticker && <p className="empty-state">Look up a ticker, or open one from Setups, Screens or the watchlist.</p>}

      {ticker && (
        <div className="stock-layout">
          <div className="chart-panel">
            <div className="toolbar chart-toolbar">
              {TIMEFRAMES.map((option) => (
                <button
                  key={option}
                  type="button"
                  className="tab"
                  aria-pressed={timeframe === option}
                  onClick={() => setTimeframe(option)}
                >
                  {option}
                </button>
              ))}
              {bars && <span className="muted">Bars as of {new Date(bars.fetched_at).toLocaleTimeString()}</span>}
            </div>
            {bars ? (
              bars.bars.length > 0 ? (
                <CandleChart
                  bars={bars.bars}
                  levels={chartLevels}
                  outline={outline}
                  vwap={bars.vwap}
                  visibleBars={VISIBLE_BARS[timeframe]}
                />
              ) : (
                <p className="empty-state">Finviz has no {timeframe} bars for {ticker}.</p>
              )
            ) : (
              <p className="muted">Loading {timeframe} bars…</p>
            )}
          </div>

          <aside className="stock-side">
            <div className="verdict-panel">
              <h3 className="editor-section-title">
                Verdict <VerdictBadge verdict={verdict} />
              </h3>
              {verdict ? (
                <ul className="verdict-reasons">
                  {verdict.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Not scanned yet. Scan this stock to get a verdict.</p>
              )}
            </div>
            <h3 className="editor-section-title">Setups</h3>
            {allSetups.length === 0 ? (
              <p className="muted">No setups in the last scan. Scan this stock to check now.</p>
            ) : (
              <ul className="setup-list">
                {allSetups.map((setup) => (
                  <li key={setup.id}>
                    <button
                      type="button"
                      className="setup-select"
                      aria-pressed={setup.id === selectedSetupId}
                      onClick={() => handleSelectSetup(setup)}
                    >
                      <span className="screen-name">
                        {patternName(setup.pattern)} <span className="muted">{setup.timeframe}</span>
                      </span>
                      <span className="screen-meta">
                        {setup.direction === "short" && !setups?.show_short_setups
                          ? `Bearish warning, breaks below ${formatPrice(setup.entry)}`
                          : `Entry ${formatPrice(setup.entry)}, stop ${formatPrice(setup.stop)}, ${setup.available_reward_risk.toFixed(1)}R`}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <QuoteTable quote={quote} error={null} isLoading={false} />
          </aside>
        </div>
      )}
    </section>
  );
}
