import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from app.finviz_client import Bar, Interval
from app.market_time import EASTERN

INTRADAY_FRESH_FOR = {"1m": timedelta(seconds=60), "5m": timedelta(seconds=300)}
REGULAR_CLOSE = time(16, 0)
SATURDAY = 5


@dataclass(frozen=True)
class BarSeries:
    bars: list[Bar]
    fetched_at: datetime


def _close_passed_between(fetched_at: datetime, now: datetime) -> bool:
    day = fetched_at.astimezone(EASTERN).date()
    last_day = now.astimezone(EASTERN).date()
    while day <= last_day:
        close = datetime.combine(day, REGULAR_CLOSE, tzinfo=EASTERN)
        if day.weekday() < SATURDAY and fetched_at < close <= now:
            return True
        day += timedelta(days=1)
    return False


def is_cache_fresh(interval: Interval, fetched_at: datetime, now: datetime) -> bool:
    if interval == "daily":
        # A daily bar only changes meaningfully at the close; until then the
        # 2-year history used for levels is unchanged.
        return not _close_passed_between(fetched_at, now)
    return now - fetched_at < INTRADAY_FRESH_FOR[interval]


def _bar_to_json(bar: Bar) -> list:
    return [bar.time.isoformat(), bar.open, bar.high, bar.low, bar.close, bar.volume]


def _bar_from_json(values: list) -> Bar:
    stored_time, open_price, high, low, close, volume = values
    return Bar(datetime.fromisoformat(stored_time).astimezone(EASTERN), open_price, high, low, close, volume)


def read_cached_bars(conn: sqlite3.Connection, ticker: str, interval: Interval) -> BarSeries | None:
    row = conn.execute(
        "SELECT fetched_at, bars FROM bar_cache WHERE ticker = ? AND interval = ?", (ticker, interval)
    ).fetchone()
    if row is None:
        return None
    bars = [_bar_from_json(values) for values in json.loads(row["bars"])]
    return BarSeries(bars, datetime.fromisoformat(row["fetched_at"]))


def write_cached_bars(conn: sqlite3.Connection, ticker: str, interval: Interval, series: BarSeries) -> None:
    conn.execute(
        """
        INSERT INTO bar_cache (ticker, interval, fetched_at, bars) VALUES (?, ?, ?, ?)
        ON CONFLICT (ticker, interval) DO UPDATE SET fetched_at = excluded.fetched_at, bars = excluded.bars
        """,
        (ticker, interval, series.fetched_at.isoformat(), json.dumps([_bar_to_json(bar) for bar in series.bars])),
    )
    conn.commit()
