import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarsResponse, fetchBars } from "../api/bars";
import { DaySetup, fetchDaySetups, fetchEntries, fetchOpenTrade, Fill, JournalEntry } from "../api/journal";
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
import { fetchJournalSettings, JournalSettings } from "../api/settings";
import { fetchNews, fetchQuote, NewsItem, Quote, refreshQuote } from "../api/stocks";
import { easternParts, easternToday } from "../easternTime";
import { finvizQuoteUrl, formatDollars, formatPrice, MISSING_VALUE } from "../format";
import { useJournalShortcuts } from "../journalShortcuts";
import { suggestShares } from "../positionSize";
import { describeSetupState } from "../setupState";
import { CandleChart, ChartLevel } from "./CandleChart";
import { DailyLossBanner } from "./DailyLossBanner";
import { NewsList } from "./NewsList";
import { PassPanel } from "./PassPanel";
import { ClickedBar, TradePanel } from "./TradePanel";
import { QuoteTable } from "./QuoteTable";
import { SlidingScaleBadge } from "./SlidingScaleBadge";
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

type JournalPanel =
  | { kind: "none" }
  | { kind: "trade"; existing: JournalEntry | null; setups: DaySetup[] }
  | { kind: "pass"; setups: DaySetup[] };

const NO_PANEL: JournalPanel = { kind: "none" };

function PositionSize({ setup, settings }: { setup: Setup; settings: JournalSettings | null }) {
  if (settings?.risk_per_trade == null) return null;
  const shares = suggestShares(settings.risk_per_trade, setup.entry, setup.stop, settings.max_position);
  return (
    <span className="screen-meta position-size">
      Size {shares} sh ({formatDollars(shares * setup.entry)}) to risk {formatDollars(settings.risk_per_trade)}
    </span>
  );
}

// The setup the panel starts on: the one picked in the side list, else the best scored that day.
function defaultSetupId(setups: DaySetup[], selectedSetupId: number | null): number | null {
  if (setups.some((setup) => setup.setup_record_id === selectedSetupId)) return selectedSetupId;
  const best = [...setups].sort((left, right) => right.score - left.score)[0];
  return best ? best.setup_record_id : null;
}

function TradePlanFigures({ setup }: { setup: Setup }) {
  // Coloured like the chart's entry, stop and target lines so the two read together.
  const figures: [string, number, string][] = [
    ["Entry", setup.entry, "entry"],
    ["Stop", setup.stop, "stop"],
    [setup.blocking_level != null ? "Target (capped)" : "Target", setup.capped_target, "target"],
  ];
  return (
    <>
      <span className="plan-figures">
        {figures.map(([label, price, kind]) => (
          <span key={kind} className="plan-figure">
            <span className="plan-label">{label}</span>
            <span className={`plan-price plan-${kind}`}>{formatPrice(price)}</span>
          </span>
        ))}
      </span>
      <span className="screen-meta">
        {setup.available_reward_risk.toFixed(1)}R · risk {setup.risk_percent.toFixed(1)}%
      </span>
    </>
  );
}

function SetupGrades({ setup }: { setup: Setup }) {
  return (
    <span className="setup-grades">
      <span className="setup-grade">
        <span className="plan-label">Score</span>
        <span className="plan-price">{setup.score.toFixed(0)}</span>
      </span>
      <span className="setup-grade">
        <span className="plan-label">Sykes</span>
        {setup.sliding_scale ? (
          <SlidingScaleBadge scale={setup.sliding_scale} ticker={setup.ticker} />
        ) : (
          <span className="plan-price">{MISSING_VALUE}</span>
        )}
      </span>
    </span>
  );
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
  // Bumped after a scan so the chart reloads the bars that scan just fetched.
  const [barsReloadCount, setBarsReloadCount] = useState(0);
  // A scan takes seconds; if the user switches stocks meanwhile, its results
  // belong to the old ticker and must not land in the new one's view.
  const shownTicker = useRef(ticker);
  shownTicker.current = ticker;
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<JournalPanel>(NO_PANEL);
  const [clickedBar, setClickedBar] = useState<ClickedBar | null>(null);
  const clickCount = useRef(0);
  const [journalSettings, setJournalSettings] = useState<JournalSettings | null>(null);
  const [loggedFills, setLoggedFills] = useState<Fill[]>([]);
  // Bumped after a save so the fill markers and daily loss banner reload.
  const [journalVersion, setJournalVersion] = useState(0);
  const [journalNotice, setJournalNotice] = useState<string | null>(null);
  const [news, setNews] = useState<NewsItem[] | null>(null);
  const [newsError, setNewsError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;
    setNews(null);
    setNewsError(null);
    let isCurrent = true;
    fetchNews(ticker)
      .then((loaded) => {
        if (isCurrent) setNews(loaded);
      })
      // Its own error: the chart and setups are still useful without news.
      .catch((loadError: unknown) => {
        if (isCurrent) setNewsError(errorMessage(loadError));
      });
    return () => {
      isCurrent = false;
    };
  }, [ticker]);

  useEffect(() => {
    fetchJournalSettings()
      .then(setJournalSettings)
      // Best effort: without settings there is simply no size suggestion.
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!ticker) return;
    let isCurrent = true;
    fetchEntries("trade", "all", ticker)
      .then((entries) => {
        if (isCurrent) setLoggedFills(entries.flatMap((entry) => entry.fills));
      })
      // Best effort: the chart is still useful without the markers.
      .catch(() => undefined);
    return () => {
      isCurrent = false;
    };
  }, [ticker, journalVersion]);

  useEffect(() => {
    setPanel(NO_PANEL);
    setClickedBar(null);
    setJournalNotice(null);
  }, [ticker]);

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
  }, [ticker, timeframe, barsReloadCount]);

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
      const [freshSetups, freshVerdict, freshQuote, freshNews] = await Promise.all([
        fetchStockSetups(scannedTicker),
        fetchStockVerdict(scannedTicker),
        refreshQuote(scannedTicker),
        // News failing must not fail the scan's other results.
        fetchNews(scannedTicker, true).catch(() => null),
      ]);
      if (shownTicker.current === scannedTicker) {
        setSetups(freshSetups);
        setVerdict(freshVerdict);
        setQuote(freshQuote);
        if (freshNews) setNews(freshNews);
        setBarsReloadCount((count) => count + 1);
      }
    } catch (scanError) {
      if (shownTicker.current === scannedTicker) {
        setError(errorMessage(scanError));
      }
    } finally {
      setIsScanning(false);
    }
  }

  const openTradePanel = useCallback(async () => {
    if (!ticker) return;
    setJournalNotice(null);
    try {
      const openTrade = await fetchOpenTrade(ticker);
      const moment = openTrade?.decided_at ?? new Date().toISOString();
      const setups = await fetchDaySetups(ticker, easternParts(moment).date, moment);
      setClickedBar(null);
      setPanel({ kind: "trade", existing: openTrade, setups });
    } catch (openError) {
      setError(errorMessage(openError));
    }
  }, [ticker]);

  const openPassPanel = useCallback(async () => {
    if (!ticker) return;
    setJournalNotice(null);
    try {
      const setups = await fetchDaySetups(ticker, easternToday(), new Date().toISOString());
      setPanel({ kind: "pass", setups });
    } catch (openError) {
      setError(errorMessage(openError));
    }
  }, [ticker]);

  const closePanel = useCallback(() => setPanel(NO_PANEL), []);

  async function startNewTrade() {
    if (!ticker) return;
    setClickedBar(null);
    try {
      // The open trade's setups were for its own day; a new trade starts from today's.
      const setups = await fetchDaySetups(ticker, easternToday(), new Date().toISOString());
      setPanel({ kind: "trade", existing: null, setups });
    } catch (startError) {
      setError(errorMessage(startError));
    }
  }

  useJournalShortcuts({ onLogTrade: openTradePanel, onPass: openPassPanel, onClose: closePanel }, Boolean(ticker));

  function handleBarClick(bar: Bar) {
    if (panel.kind !== "trade") return;
    clickCount.current += 1;
    setClickedBar({ bar, id: clickCount.current });
  }

  function handleJournalSaved(entry: JournalEntry) {
    setPanel(NO_PANEL);
    setJournalVersion((version) => version + 1);
    const saved = entry.kind === "pass" ? "Pass saved to the journal." : "Trade saved to the journal.";
    setJournalNotice(entry.bar_warning ? `${saved} ${entry.bar_warning}` : saved);
  }

  function handleSelectSetup(setup: Setup | Warning) {
    setSelectedSetupId(setup.id);
    setTimeframe(setup.timeframe);
  }

  return (
    <section className="stock-view">
      <DailyLossBanner refreshKey={journalVersion} />
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
              <span className="journal-buttons">
                <button type="button" onClick={openTradePanel} title="Log a trade (L)">
                  Log trade
                </button>
                <button type="button" onClick={openPassPanel} title="Pass on this stock (P)">
                  Pass
                </button>
              </span>
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
                    isDaily={timeframe === "daily"}
                    markers={hasSessions ? loggedFills : undefined}
                    news={news ?? undefined}
                    // A daily candle has no time of day to fill at.
                    onBarClick={hasSessions ? handleBarClick : undefined}
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
            {journalNotice && (
              <p role="status" className="muted journal-notice">
                {journalNotice}
              </p>
            )}
            {panel.kind === "trade" && (
              <>
                {panel.existing && (
                  <p className="muted">
                    Adding to your open {ticker} trade.{" "}
                    <button type="button" onClick={startNewTrade}>
                      Start a new trade instead
                    </button>
                  </p>
                )}
                <TradePanel
                  key={panel.existing?.id ?? "new"}
                  ticker={ticker}
                  setups={panel.setups}
                  defaultSetupId={defaultSetupId(panel.setups, selectedSetupId)}
                  existing={panel.existing}
                  settings={journalSettings}
                  clickedBar={clickedBar}
                  onSaved={handleJournalSaved}
                  onClose={closePanel}
                />
              </>
            )}
            {panel.kind === "pass" && (
              <PassPanel
                ticker={ticker}
                setups={panel.setups}
                defaultSetupId={defaultSetupId(panel.setups, selectedSetupId)}
                onSaved={handleJournalSaved}
                onClose={closePanel}
              />
            )}
            {/* After the panels, so opening one pushes the news down and the chart stays put. */}
            <NewsList key={ticker} items={news} error={newsError} />
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
                      <span className="setup-heading">
                        <span className="screen-name">
                          {patternName(setup.pattern)} <span className="muted">{setup.timeframe}</span>
                        </span>
                        <span className="screen-meta">{describeSetupState(setup)}</span>
                      </span>
                      {isTradeSetup(setup) ? (
                        <>
                          <TradePlanFigures setup={setup} />
                          <PositionSize setup={setup} settings={journalSettings} />
                        </>
                      ) : (
                        <span className="screen-meta">Bearish warning, breaks below {formatPrice(setup.entry)}</span>
                      )}
                    </button>
                    {/* Outside the select button: the Sykes grade is its own button. */}
                    {isTradeSetup(setup) && <SetupGrades setup={setup} />}
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
