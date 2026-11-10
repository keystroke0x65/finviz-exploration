"""Keeps the 1-minute bars of each journal entry's days after Finviz drops them.

Finviz returns about two weeks of 1-minute bars, so a trade's chart would be
gone a fortnight later. Each (stock, trading day) is stored once, from 4:00 AM
to 8:00 PM ET, and shared by every entry on that day.
"""

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Literal

from app.bars.loader import FetchBars
from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import Bar
from app.journal.positions import compute_trade_figures
from app.journal.store import NewEntry, list_entries
from app.market_time import EASTERN

logger = logging.getLogger(__name__)

# partial: saved before 8 PM, more to come. complete: the whole day. missing: Finviz no longer
# had the day when first asked. incomplete: part of the day was saved, then Finviz dropped it.
BarDayStatus = Literal["partial", "complete", "missing", "incomplete"]
FINAL_STATUSES = ("complete", "missing", "incomplete")

DAY_START = time(4, 0)
DAY_END = time(20, 0)
SATURDAY = 5
BARS_RETRY_WARNING = "Chart bars not saved yet, will retry."
# One request per stock at Finviz's 1 req/s pacing; the next tick does the rest.
MAX_TICKERS_PER_RUN = 20


def _eastern_day(moment: datetime) -> date:
    return moment.astimezone(EASTERN).date()


def _weekdays(start: date, end: date) -> list[date]:
    days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    return [day for day in days if day.weekday() < SATURDAY]


def days_needed(entry: NewEntry, now: datetime) -> list[date]:
    if entry.kind == "pass" or not entry.fills:
        return [_eastern_day(entry.decided_at)]
    figures = compute_trade_figures(entry.direction, entry.fills, entry.plan_stop, entry.plan_target, entry.fees, now)
    last_day = _eastern_day(figures.last_fill_at if figures.status == "closed" else now)
    return _weekdays(_eastern_day(figures.opened_at), last_day)


def _read_statuses(conn: sqlite3.Connection, ticker: str, days: list[date]) -> dict[date, BarDayStatus | None]:
    statuses: dict[date, BarDayStatus | None] = {day: None for day in days}
    for row in conn.execute("SELECT day, status FROM journal_bar_days WHERE ticker = ?", (ticker,)):
        day = date.fromisoformat(row["day"])
        if day in statuses:
            statuses[day] = row["status"]
    return statuses


def _group_session_bars(bars: list[Bar]) -> dict[date, list[Bar]]:
    by_day: dict[date, list[Bar]] = defaultdict(list)
    for bar in bars:
        eastern = bar.time.astimezone(EASTERN)
        if DAY_START <= eastern.time() < DAY_END:
            by_day[eastern.date()].append(bar)
    return by_day


def _encode_bars(bars: list[Bar]) -> str:
    return json.dumps([[bar.time.isoformat(), bar.open, bar.high, bar.low, bar.close, bar.volume] for bar in bars])


def _decode_bars(stored: str) -> list[Bar]:
    return [Bar(datetime.fromisoformat(moment), *values) for moment, *values in json.loads(stored)]


def _write_day(conn: sqlite3.Connection, ticker: str, day: date, status: BarDayStatus, bars: list[Bar], now: datetime) -> None:
    conn.execute(
        """
        INSERT INTO journal_bar_days (ticker, day, status, saved_at, bars) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (ticker, day) DO UPDATE SET status = excluded.status, saved_at = excluded.saved_at, bars = excluded.bars
        """,
        (ticker, day.isoformat(), status, now.isoformat(), _encode_bars(bars)),
    )


def _status_for(day: date, fetched: list[Bar], saved: list[Bar], oldest_day: date, now: datetime) -> BarDayStatus | None:
    """None: nothing to save yet (today or later, no bars so far)."""
    if fetched:
        is_over = now >= datetime.combine(day, DAY_END, tzinfo=EASTERN)
        return "complete" if is_over else "partial"
    # Before Finviz's history starts, or a past day with no trading (holiday).
    is_gone = day < oldest_day or day < _eastern_day(now)
    if not is_gone:
        return None
    # Keep what was saved: an empty fetch must never wipe a chart.
    return "incomplete" if saved else "missing"


def _merge(saved: list[Bar], fetched: list[Bar]) -> list[Bar]:
    """Saved bars plus fetched ones; a fetched bar replaces the saved bar at the same minute."""
    by_time = {bar.time: bar for bar in saved}
    by_time.update({bar.time: bar for bar in fetched})
    return [by_time[moment] for moment in sorted(by_time)]


def _saved_bars(conn: sqlite3.Connection, ticker: str, day: date) -> list[Bar]:
    row = conn.execute(
        "SELECT bars FROM journal_bar_days WHERE ticker = ? AND day = ?", (ticker, day.isoformat())
    ).fetchone()
    return [] if row is None else _decode_bars(row["bars"])


def save_bar_days(conn: sqlite3.Connection, ticker: str, days: list[date], now: datetime, fetch_bars_fn: FetchBars) -> None:
    """Save every listed day not already complete or missing. Finviz errors propagate."""
    statuses = _read_statuses(conn, ticker, days)
    to_save = [day for day, status in statuses.items() if status not in FINAL_STATUSES]
    if not to_save:
        return
    fetched = fetch_bars_fn(ticker, "1m")
    if not fetched:
        return
    by_day = _group_session_bars(fetched)
    oldest_day = min(_eastern_day(bar.time) for bar in fetched)
    with conn:
        for day in to_save:
            saved = _saved_bars(conn, ticker, day)
            fetched_day = by_day.get(day, [])
            status = _status_for(day, fetched_day, saved, oldest_day, now)
            if status is not None:
                _write_day(conn, ticker, day, status, _merge(saved, fetched_day), now)


def read_bars(conn: sqlite3.Connection, ticker: str, days: list[date]) -> tuple[list[Bar], dict[date, BarDayStatus | None]]:
    statuses = _read_statuses(conn, ticker, days)
    bars: list[Bar] = []
    for day in days:
        bars.extend(_saved_bars(conn, ticker, day))
    return sorted(bars, key=lambda bar: bar.time), statuses


def save_bars_for_entry(conn: sqlite3.Connection, entry: NewEntry, now: datetime, fetch_bars_fn: FetchBars) -> str | None:
    """Save the entry's bars; on a Finviz failure return a warning instead (the background job retries)."""
    try:
        save_bar_days(conn, entry.ticker, days_needed(entry, now), now, fetch_bars_fn)
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        logger.warning("could not save journal bars for %s: %s", entry.ticker, exc)
        return BARS_RETRY_WARNING
    return None


def _pending_days_by_ticker(conn: sqlite3.Connection, now: datetime) -> dict[str, list[date]]:
    pending: dict[str, set[date]] = defaultdict(set)
    for entry in list_entries(conn):
        days = days_needed(entry, now)
        statuses = _read_statuses(conn, entry.ticker, days)
        pending[entry.ticker].update(day for day, status in statuses.items() if status not in FINAL_STATUSES)
    return {ticker: sorted(days) for ticker, days in pending.items() if days}


def complete_pending_days(conn: sqlite3.Connection, now: datetime, fetch_bars_fn: FetchBars) -> int:
    """Save every entry's unsaved or partial days; returns how many stocks were fetched."""
    fetched = 0
    for ticker, days in list(_pending_days_by_ticker(conn, now).items())[:MAX_TICKERS_PER_RUN]:
        try:
            save_bar_days(conn, ticker, days, now, fetch_bars_fn)
        except (FinvizAuthError, FinvizRateLimitError) as exc:
            # Every further request would fail the same way; the next run retries.
            logger.warning("journal bar saving stopped at %s: %s", ticker, exc)
            return fetched
        except FinvizUnavailableError as exc:
            logger.warning("could not save journal bars for %s: %s", ticker, exc)
            continue
        fetched += 1
    return fetched


def aggregate_bars(bars: list[Bar], minutes: int) -> list[Bar]:
    """Combine 1-minute bars into bars of `minutes`, aligned to the clock (9:30, 9:35, ...)."""
    buckets: dict[datetime, list[Bar]] = defaultdict(list)
    for bar in sorted(bars, key=lambda item: item.time):
        start = bar.time.replace(minute=bar.time.minute - bar.time.minute % minutes, second=0, microsecond=0)
        buckets[start].append(bar)
    return [
        Bar(start, group[0].open, max(item.high for item in group), min(item.low for item in group), group[-1].close,
            sum(item.volume for item in group))
        for start, group in sorted(buckets.items())
    ]
