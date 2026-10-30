"""Runs pattern detection over a ticker's bars and records what it finds."""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, time
from typing import Callable

from app.bars.loader import load_bars
from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import Bar, Interval, ScreenRow, get_bars, get_snapshots, run_screen
from app.market_time import EASTERN
from app.patterns.candles import candle_points
from app.patterns.detectors import run_detectors
from app.patterns.indicators import session_levels, session_vwap
from app.patterns.levels import find_daily_levels
from app.patterns.ranking import score_setup
from app.patterns.sliding_scale import MarketGainers, SlidingScaleInputs, count_spike_days, grade_sliding_scale
from app.patterns.trade_plan import TradePlan, build_trade_plan, classify_state, find_trigger_time
from app.patterns.types import DetectorContext, PatternMatch, SetupState
from app.patterns.verdict import Verdict, compute_verdict
from app.scanning.active import select_active_tickers
from app.scanning.market_gainers import (
    MARKET_MOVERS_FILTERS,
    count_big_gainers,
    read_market_gainers,
    save_market_gainers,
)
from app.scanning.snapshots import save_snapshots
from app.scanning.verdicts import save_verdict
from app.setups.resolver import has_deadline_passed, resolve_outcome
from app.setups.track_record import PatternStats, stats_for
from app.setups.store import (
    list_open_records,
    list_tickers_with_open_records,
    mark_ticker_scanned,
    record_match,
    save_outcome,
)
from app.watchlist.run_status import get_last_feeder_run
from app.watchlist.store import list_entries

logger = logging.getLogger(__name__)

TIMEFRAMES: list[Interval] = ["daily", "5m", "1m"]
# Enough recent bars to find a swing for the trailing stop.
TRAILING_STOP_BARS = 30
# Morning/evening stars need the last three bars.
CANDLE_BARS = 3
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
SNAPSHOT_FAILURE_LABEL = "watchlist prices"
RATE_LIMIT_SKIPPED_REASON = "skipped: Finviz is rate limiting requests"
AUTH_SKIPPED_REASON = "skipped: Finviz rejected the auth token"
# Inactive tickers whose setups have passed their deadline, settled per scan.
MAX_INACTIVE_RESOLUTIONS = 10


@dataclass(frozen=True)
class ScanDeps:
    fetch_bars: Callable[[str, Interval], list[Bar]]
    fetch_snapshots: Callable[[list[str]], list[ScreenRow]]
    # None skips the market count; the sliding scale's market factor then shows "no data".
    fetch_market_movers: Callable[[], list[ScreenRow]] | None = None


def _fetch_finviz_market_movers() -> list[ScreenRow]:
    return run_screen(MARKET_MOVERS_FILTERS, None, None).rows


def finviz_scan_deps() -> ScanDeps:
    return ScanDeps(fetch_bars=get_bars, fetch_snapshots=get_snapshots, fetch_market_movers=_fetch_finviz_market_movers)


@dataclass(frozen=True)
class ScanResult:
    scanned: list[str]
    failed: list[tuple[str, str]]
    setups_found: int
    scanned_at: datetime


def _session_label(match: PatternMatch) -> str:
    if match.timeframe == "daily":
        return "daily"
    clock = match.detected_at.astimezone(EASTERN).time()
    if clock < REGULAR_OPEN:
        return "pre-market"
    return "regular" if clock < REGULAR_CLOSE else "after-hours"


def _detect_all(bars_by_timeframe: dict[Interval, list[Bar]], now: datetime) -> list[PatternMatch]:
    daily = bars_by_timeframe["daily"]
    daily_levels = find_daily_levels(daily)
    today = now.astimezone(EASTERN).date()
    matches: list[PatternMatch] = []
    for timeframe in TIMEFRAMES:
        bars = bars_by_timeframe[timeframe]
        if not bars:
            continue
        is_intraday = timeframe != "daily"
        # Before a stock trades today (the 4:00 AM scan, a halt, a thin
        # pre-market) its latest intraday bars are from an earlier day; patterns
        # in them aren't current setups.
        if is_intraday and bars[-1].time.astimezone(EASTERN).date() != today:
            continue
        context = DetectorContext(
            timeframe=timeframe,
            daily_levels=daily_levels,
            session=session_levels(bars, daily, today) if is_intraday else None,
            vwap=session_vwap(bars) if is_intraday else None,
        )
        matches.extend(run_detectors(bars, context))
    return matches


def _todays_bars(bars: list[Bar], now: datetime) -> list[Bar]:
    today = now.astimezone(EASTERN).date()
    return [bar for bar in bars if bar.time.astimezone(EASTERN).date() == today]


def _verdict_for(
    bars_by_timeframe: dict[Interval, list[Bar]],
    matches: list[PatternMatch],
    now: datetime,
    relative_volume: float | None,
) -> Verdict:
    # Only today's intraday bars say anything about how the stock is trading now.
    one_minute = _todays_bars(bars_by_timeframe["1m"], now)
    five_minute = _todays_bars(bars_by_timeframe["5m"], now)
    daily = bars_by_timeframe["daily"]
    return compute_verdict(
        one_minute, five_minute, daily, session_vwap(one_minute) if one_minute else None,
        find_daily_levels(daily), matches, relative_volume=relative_volume,
    )


@dataclass(frozen=True)
class _UsableSetup:
    match: PatternMatch
    plan: TradePlan
    state: SetupState
    triggered_at: datetime | None


def _todays_intraday_bars(bars_by_timeframe: dict[Interval, list[Bar]], now: datetime) -> list[Bar]:
    """Today's 1m bars, else today's 5m bars, else none."""
    for intraday in ("1m", "5m"):
        todays = _todays_bars(bars_by_timeframe[intraday], now)
        if todays:
            return todays
    return []


def _latest_price(bars_by_timeframe: dict[Interval, list[Bar]], timeframe: Interval, now: datetime) -> float:
    # Daily bars are cached until the close, so a daily setup's state would be
    # hours stale; today's intraday close is the current price when there is one.
    if timeframe == "daily":
        todays = _todays_intraday_bars(bars_by_timeframe, now)
        if todays:
            return todays[-1].close
    return bars_by_timeframe[timeframe][-1].close


def _price_path(bars_by_timeframe: dict[Interval, list[Bar]], timeframe: Interval, now: datetime) -> list[Bar]:
    """Bars to find a trigger in; daily setups get today's intraday bars in place of
    the cached daily bar, matching how their state is judged."""
    if timeframe != "daily":
        return bars_by_timeframe[timeframe]
    todays = _todays_intraday_bars(bars_by_timeframe, now)
    if not todays:
        return bars_by_timeframe["daily"]
    today = now.astimezone(EASTERN).date()
    earlier_days = [bar for bar in bars_by_timeframe["daily"] if bar.time.astimezone(EASTERN).date() < today]
    return earlier_days + todays


def _usable_setups(
    matches: list[PatternMatch], bars_by_timeframe: dict[Interval, list[Bar]], now: datetime
) -> list[_UsableSetup]:
    """Matches that give a valid plan and aren't already past their stop.

    Only these become setups, and only these count as evidence in the verdict.
    """
    daily_levels = find_daily_levels(bars_by_timeframe["daily"])
    usable: list[_UsableSetup] = []
    for match in matches:
        bars = bars_by_timeframe[match.timeframe]
        plan = build_trade_plan(match, daily_levels, bars[-TRAILING_STOP_BARS:])
        if plan is None:
            continue
        state = classify_state(plan, _latest_price(bars_by_timeframe, match.timeframe, now))
        # A setup already past its stop isn't a setup; recording it would also
        # skew outcome stats with trades nobody could have taken.
        if state == "invalidated":
            continue
        triggered_at = (
            find_trigger_time(plan, _price_path(bars_by_timeframe, match.timeframe, now))
            if state in ("triggered", "extended")
            else None
        )
        usable.append(_UsableSetup(match, plan, state, triggered_at))
    return usable


def _record_setups(
    conn: sqlite3.Connection,
    ticker: str,
    setups: list[_UsableSetup],
    bars_by_timeframe: dict[Interval, list[Bar]],
    snapshot: ScreenRow | None,
    now: datetime,
    verdict_call: str | None,
    market_gainers: MarketGainers | None,
) -> int:
    matches = [setup.match for setup in setups]
    daily = bars_by_timeframe["daily"]
    spike_days = count_spike_days(daily, now.astimezone(EASTERN).date()) if daily else None
    relative_volume = snapshot.relative_volume if snapshot else None
    float_millions = snapshot.float_millions if snapshot else None
    history: dict[tuple[str, str], PatternStats | None] = {}
    for setup in setups:
        key = (setup.match.pattern, setup.match.timeframe)
        if key not in history:
            history[key] = stats_for(conn, *key)
        others = [other for other in matches if other is not setup.match]
        recent_bars = bars_by_timeframe[setup.match.timeframe][-CANDLE_BARS:]
        score = score_setup(
            setup.match, setup.plan, setup.state, relative_volume, others,
            track_record=history[key], candle_points=candle_points(setup.plan, recent_bars),
        )
        sliding_scale = grade_sliding_scale(
            SlidingScaleInputs(
                quality=setup.match.quality, state=setup.state, reward_risk=setup.plan.available_reward_risk,
                snapshot=snapshot, spike_days=spike_days, setup_time=setup.triggered_at or now,
                market_gainers=market_gainers, now=now,
            )
        )
        record_match(
            conn, ticker, setup.match, setup.plan, setup.state, score, _session_label(setup.match),
            float_millions, now, verdict=verdict_call, triggered_at=setup.triggered_at, sliding_scale=sliding_scale,
        )
    return len(setups)


def _resolve_open_records(
    conn: sqlite3.Connection, ticker: str, bars_by_timeframe: dict[Interval, list[Bar]], now: datetime
) -> None:
    for record in list_open_records(conn, ticker):
        resolution = resolve_outcome(record, bars_by_timeframe[record.timeframe], now)
        if resolution.outcome != "open":
            save_outcome(conn, record.id, resolution)


def _resolve_inactive_tickers(conn: sqlite3.Connection, skip: set[str], now: datetime, deps: ScanDeps) -> None:
    """Settle setups of tickers that dropped out of the active set.

    Otherwise their records would stay open forever, and Finviz only keeps
    about two weeks of 1m bars to resolve them from.
    """
    due = [
        ticker
        for ticker in list_tickers_with_open_records(conn)
        if ticker not in skip and any(has_deadline_passed(record, now) for record in list_open_records(conn, ticker))
    ][:MAX_INACTIVE_RESOLUTIONS]
    for ticker in due:
        try:
            needed = {record.timeframe for record in list_open_records(conn, ticker)}
            bars = {timeframe: load_bars(conn, ticker, timeframe, now, deps.fetch_bars).bars for timeframe in needed}
            _resolve_open_records(conn, ticker, bars, now)
        except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
            # Best effort: the next scan tries again.
            logger.warning("could not resolve setups for %s: %s", ticker, exc)
            return


def scan_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    snapshot: ScreenRow | None,
    now: datetime,
    deps: ScanDeps,
    should_refresh_intraday: bool = False,
    market_gainers: MarketGainers | None = None,
) -> int:
    # Daily bars stay cached even on a refresh: today's price comes from the
    # intraday bars, and the daily history only changes at the close.
    bars_by_timeframe = {
        timeframe: load_bars(
            conn, ticker, timeframe, now, deps.fetch_bars,
            should_use_cache=timeframe == "daily" or not should_refresh_intraday,
        ).bars
        for timeframe in TIMEFRAMES
    }
    setups = _usable_setups(_detect_all(bars_by_timeframe, now), bars_by_timeframe, now)
    relative_volume = snapshot.relative_volume if snapshot else None
    verdict = _verdict_for(bars_by_timeframe, [setup.match for setup in setups], now, relative_volume)
    save_verdict(conn, ticker, verdict, now)
    recorded = _record_setups(conn, ticker, setups, bars_by_timeframe, snapshot, now, verdict.call, market_gainers)
    _resolve_open_records(conn, ticker, bars_by_timeframe, now)
    mark_ticker_scanned(conn, ticker, now)
    return recorded


def _screen_hits(conn: sqlite3.Connection) -> set[str]:
    last_run = get_last_feeder_run(conn)
    if last_run is None:
        return set()
    return set(last_run.result.tickers_added) | set(last_run.result.tickers_updated)


def _fetch_snapshots(deps: ScanDeps, tickers: list[str]) -> tuple[dict[str, ScreenRow], str | None]:
    try:
        rows = deps.fetch_snapshots(tickers)
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        return {}, str(exc)
    return {row.ticker: row for row in rows}, None


def _count_market_gainers(conn: sqlite3.Connection, deps: ScanDeps, now: datetime) -> None:
    if deps.fetch_market_movers is None:
        return
    try:
        rows = deps.fetch_market_movers()
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        # Best effort: without today's count the market factor shows "no data",
        # which shouldn't cost the whole scan.
        logger.warning("could not count market gainers: %s", exc)
        return
    save_market_gainers(conn, count_big_gainers(rows), now)


def run_scan(
    conn: sqlite3.Connection,
    now: datetime,
    deps: ScanDeps,
    tickers: list[str] | None = None,
    should_refresh_intraday: bool = False,
) -> ScanResult:
    """Scan explicit tickers, or (tickers=None) the active part of the watchlist.

    should_refresh_intraday fetches new 1m/5m bars even when cached ones are
    still fresh, for a scan someone asked for to see the latest move.
    """
    failed: list[tuple[str, str]] = []
    if tickers is None:
        watchlist = [entry.ticker for entry in list_entries(conn)]
        snapshots, snapshot_error = _fetch_snapshots(deps, watchlist)
        if snapshot_error is not None:
            return ScanResult([], [(SNAPSHOT_FAILURE_LABEL, snapshot_error)], 0, now)
        save_snapshots(conn, list(snapshots.values()), now)
        tickers = select_active_tickers(list(snapshots.values()), _screen_hits(conn))
        _count_market_gainers(conn, deps, now)
    else:
        # Snapshots only improve the score here (relative volume), so a failure
        # to get them doesn't stop an explicit scan.
        snapshots, _ = _fetch_snapshots(deps, tickers)
    # One-stock scans reuse the latest full scan's count from today.
    market_gainers = read_market_gainers(conn, now)

    scanned: list[str] = []
    setups_found = 0
    was_stopped_by_finviz = False
    for index, ticker in enumerate(tickers):
        try:
            setups_found += scan_ticker(
                conn, ticker, snapshots.get(ticker), now, deps,
                should_refresh_intraday=should_refresh_intraday, market_gainers=market_gainers,
            )
        except FinvizAuthError as exc:
            # Every later request would fail the same way.
            failed.append((ticker, str(exc)))
            skipped = tickers[index + 1 :]
            if skipped:
                failed.append((", ".join(skipped), AUTH_SKIPPED_REASON))
            was_stopped_by_finviz = True
            break
        except FinvizRateLimitError as exc:
            # Back off: more requests now would only be refused too and could
            # prolong the throttling. The next scheduled scan picks them up.
            failed.append((ticker, str(exc)))
            skipped = tickers[index + 1 :]
            if skipped:
                failed.append((", ".join(skipped), RATE_LIMIT_SKIPPED_REASON))
            was_stopped_by_finviz = True
            break
        except FinvizUnavailableError as exc:
            failed.append((ticker, str(exc)))
            continue
        except Exception as exc:
            # A bug or odd data for one stock must not cost the rest of the scan.
            logger.exception("scan of %s failed", ticker)
            failed.append((ticker, f"internal error ({type(exc).__name__}); see backend logs"))
            continue
        scanned.append(ticker)
    if not was_stopped_by_finviz:
        _resolve_inactive_tickers(conn, set(tickers), now, deps)
    return ScanResult(scanned, failed, setups_found, now)
