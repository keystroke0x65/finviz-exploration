import { useEffect, useMemo, useRef, useState } from "react";
import { BarsResponse, fetchBars } from "../api/bars";
import {
  fetchStockSetups,
  fetchStockVerdict,
  isTradeSetup,
  patternName,
  runScan,
  Setup,
  SetupsResponse,
  Timeframe,
  Verdict,
  Warning,
} from "../api/setups";
import { fetchQuote, Quote } from "../api/stocks";
import { finvizQuoteUrl, formatPrice } from "../format";
import { describeSetupState } from "../setupState";
import { CandleChart, ChartLevel } from "./CandleChart";
import { QuoteTable } from "./QuoteTable";
import { StockSearch } from "./StockSearch";
import { describeVerdictAge, VerdictBadge } from "./VerdictBadge";

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

function setupLevels(setup: Setup | Warning): ChartLevel[] {
  // Warnings carry no trade plan: only the breakdown level is drawn.
  if (!isTradeSetup(setup)) {
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
  // Daily bars have no pre-market or after-hours part to shade.
  const hasSessions = timeframe !== "daily";
  const [bars, setBars] = useState<BarsResponse | null>(null);
  const [setups, setSetups] = useState<SetupsResponse | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [selectedSetupId, setSelectedSetupId] = useState<number | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  // A scan takes seconds; if the user switches stocks meanwhile, its results
  // belong to the old ticker and must not land in the new one's view.
  const shownTicker = useRef(ticker);
  shownTicker.current = ticker;
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) {
      return;
    }
    setSelectedSetupId(null);
    setQuote(null);
    setVerdict(null);
    // A response for a ticker the user has already left must not overwrite the new one.
    let isCurrent = true;
    const ifCurrent = <T,>(apply: (value: T) => void) => (value: T) => {
      if (isCurrent) apply(value);
    };
    Promise.all([
      fetchStockSetups(ticker).then(ifCurrent(setSetups)),
      fetchQuote(ticker).then(ifCurrent(setQuote)),
      fetchStockVerdict(ticker).then(ifCurrent(setVerdict)),
    ]).catch(ifCurrent((loadError: unknown) => setError(errorMessage(loadError))));
    return () => {
      isCurrent = false;
    };
  }, [ticker]);

  useEffect(() => {
    if (!ticker) {
      return;
    }
    setError(null);
    setBars(null);
    let isCurrent = true;
    fetchBars(ticker, timeframe)
      .then((loaded) => {
        if (isCurrent) setBars(loaded);
      })
      .catch((loadError) => {
        if (isCurrent) setError(errorMessage(loadError));
      });
    return () => {
      isCurrent = false;
    };
  }, [ticker, timeframe]);

  const allSetups = useMemo<(Setup | Warning)[]>(
    () => [...(setups?.setups ?? []), ...(setups?.warnings ?? [])],
    [setups],
  );
  const selectedSetup = allSetups.find((setup) => setup.id === selectedSetupId) ?? null;

  const chartLevels = useMemo(() => {
    if (!bars) {
      return [];
    }
    const selectedLevels = selectedSetup ? setupLevels(selectedSetup) : [];
    return [...nearbyDailyLevels(bars), ...sessionLevels(bars), ...selectedLevels];
  }, [bars, selectedSetup]);

  const outline = selectedSetup && selectedSetup.timeframe === timeframe ? selectedSetup.key_points : null;

  async function handleScan() {
    if (!ticker) {
      return;
    }
    const scannedTicker = ticker;
    setIsScanning(true);
    setError(null);
    try {
      await runScan(scannedTicker);
      const [freshSetups, freshVerdict] = await Promise.all([
        fetchStockSetups(scannedTicker),
        fetchStockVerdict(scannedTicker),
      ]);
      if (shownTicker.current === scannedTicker) {
        setSetups(freshSetups);
        setVerdict(freshVerdict);
      }
    } catch (scanError) {
      if (shownTicker.current === scannedTicker) {
        setError(errorMessage(scanError));
      }
    } finally {
      setIsScanning(false);
    }
  }

  function handleSelectSetup(setup: Setup | Warning) {
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
                <>
                  <CandleChart
                    bars={bars.bars}
                    levels={chartLevels}
                    outline={outline}
                    vwap={bars.vwap}
                    visibleBars={VISIBLE_BARS[timeframe]}
                    shadeSessions={hasSessions}
                  />
                  {hasSessions && (
                    <p className="chart-legend muted">
                      <span className="legend-item">
                        <span className="legend-swatch" data-session="pre-market" />
                        Pre-market
                      </span>
                      <span className="legend-item">
                        <span className="legend-swatch" data-session="after-hours" />
                        After-hours
                      </span>
                    </p>
                  )}
                </>
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
                <>
                  <ul className="verdict-reasons">
                    {verdict.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                  <p className="muted verdict-age">{describeVerdictAge(verdict)}</p>
                </>
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
                        {describeSetupState(setup)} ·{" "}
                        {isTradeSetup(setup)
                          ? `Entry ${formatPrice(setup.entry)}, stop ${formatPrice(setup.stop)}, ${setup.available_reward_risk.toFixed(1)}R`
                          : `Bearish warning, breaks below ${formatPrice(setup.entry)}`}
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
