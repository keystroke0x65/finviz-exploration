"""Runs pattern detection over a ticker's bars and records what it finds."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, time
from typing import Callable

from app.bars.loader import load_bars
from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import Bar, Interval, ScreenRow
from app.market_time import EASTERN
from app.patterns.detectors import run_detectors
from app.patterns.indicators import session_levels, session_vwap
from app.patterns.levels import find_daily_levels
from app.patterns.ranking import score_setup
from app.patterns.trade_plan import build_trade_plan, classify_state
from app.patterns.types import DetectorContext, PatternMatch
from app.scanning.active import select_active_tickers
from app.scanning.snapshots import save_snapshots
from app.setups.resolver import resolve_outcome
from app.setups.store import list_open_records, mark_ticker_scanned, record_match, save_outcome
from app.watchlist.run_status import get_last_feeder_run
from app.watchlist.store import list_entries

TIMEFRAMES: list[Interval] = ["daily", "5m", "1m"]
# Enough recent bars to find a swing for the trailing stop.
TRAILING_STOP_BARS = 30
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
SNAPSHOT_FAILURE_LABEL = "watchlist prices"


@dataclass(frozen=True)
class ScanDeps:
    fetch_bars: Callable[[str, Interval], list[Bar]]
    fetch_snapshots: Callable[[list[str]], list[ScreenRow]]


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
        context = DetectorContext(
            timeframe=timeframe,
            daily_levels=daily_levels,
            session=session_levels(bars, daily, today) if is_intraday else None,
            vwap=session_vwap(bars) if is_intraday else None,
        )
        matches.extend(run_detectors(bars, context))
    return matches


def _record_matches(
    conn: sqlite3.Connection,
    ticker: str,
    matches: list[PatternMatch],
    bars_by_timeframe: dict[Interval, list[Bar]],
    snapshot: ScreenRow | None,
    now: datetime,
) -> int:
    daily_levels = find_daily_levels(bars_by_timeframe["daily"])
    recorded = 0
    for match in matches:
        bars = bars_by_timeframe[match.timeframe]
        plan = build_trade_plan(match, daily_levels, bars[-TRAILING_STOP_BARS:])
        if plan is None:
            continue
        state = classify_state(plan, bars[-1].close)
        # A setup already past its stop isn't a setup; recording it would also
        # skew outcome stats with trades nobody could have taken.
        if state == "invalidated":
            continue
        others = [other for other in matches if other is not match]
        score = score_setup(match, plan, state, snapshot.relative_volume if snapshot else None, others)
        float_millions = snapshot.float_millions if snapshot else None
        record_match(conn, ticker, match, plan, state, score, _session_label(match), float_millions, now)
        recorded += 1
    return recorded


def _resolve_open_records(
    conn: sqlite3.Connection, ticker: str, bars_by_timeframe: dict[Interval, list[Bar]], now: datetime
) -> None:
    for record in list_open_records(conn, ticker):
        resolution = resolve_outcome(record, bars_by_timeframe[record.timeframe], now)
        if resolution.outcome != "open":
            save_outcome(conn, record.id, resolution)


def scan_ticker(conn: sqlite3.Connection, ticker: str, snapshot: ScreenRow | None, now: datetime, deps: ScanDeps) -> int:
    bars_by_timeframe = {
        timeframe: load_bars(conn, ticker, timeframe, now, deps.fetch_bars).bars for timeframe in TIMEFRAMES
    }
    matches = _detect_all(bars_by_timeframe, now)
    recorded = _record_matches(conn, ticker, matches, bars_by_timeframe, snapshot, now)
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


def run_scan(
    conn: sqlite3.Connection, now: datetime, deps: ScanDeps, tickers: list[str] | None = None
) -> ScanResult:
    """Scan explicit tickers, or (tickers=None) the active part of the watchlist."""
    failed: list[tuple[str, str]] = []
    if tickers is None:
        watchlist = [entry.ticker for entry in list_entries(conn)]
        snapshots, snapshot_error = _fetch_snapshots(deps, watchlist)
        if snapshot_error is not None:
            return ScanResult([], [(SNAPSHOT_FAILURE_LABEL, snapshot_error)], 0, now)
        save_snapshots(conn, list(snapshots.values()), now)
        tickers = select_active_tickers(list(snapshots.values()), _screen_hits(conn))
    else:
        # Snapshots only improve the score here (relative volume), so a failure
        # to get them doesn't stop an explicit scan.
        snapshots, _ = _fetch_snapshots(deps, tickers)

    scanned: list[str] = []
    setups_found = 0
    for ticker in tickers:
        try:
            setups_found += scan_ticker(conn, ticker, snapshots.get(ticker), now, deps)
        except FinvizAuthError as exc:
            # Every later request would fail the same way.
            failed.append((ticker, str(exc)))
            break
        except (FinvizRateLimitError, FinvizUnavailableError) as exc:
            failed.append((ticker, str(exc)))
            continue
        scanned.append(ticker)
    return ScanResult(scanned, failed, setups_found, now)
