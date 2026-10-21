import sqlite3
from datetime import datetime
from typing import Callable

from app.bars.cache import BarSeries, is_cache_fresh, read_cached_bars, write_cached_bars
from app.finviz_client import Bar, Interval

FetchBars = Callable[[str, Interval], list[Bar]]


def load_bars(
    conn: sqlite3.Connection, ticker: str, interval: Interval, now: datetime, fetch_bars_fn: FetchBars
) -> BarSeries:
    cached = read_cached_bars(conn, ticker, interval)
    if cached is not None and is_cache_fresh(interval, cached.fetched_at, now):
        return cached
    series = BarSeries(fetch_bars_fn(ticker, interval), now)
    write_cached_bars(conn, ticker, interval, series)
    return series
