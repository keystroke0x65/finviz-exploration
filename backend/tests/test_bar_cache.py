from datetime import datetime, timedelta

from app.bars.cache import BarSeries, is_cache_fresh, read_cached_bars, write_cached_bars
from app.bars.loader import load_bars
from app.finviz_client import Bar
from app.market_time import EASTERN

TUESDAY_10AM = datetime(2026, 10, 20, 10, 0, tzinfo=EASTERN)
BARS = [Bar(datetime(2026, 10, 20, 9, 30, tzinfo=EASTERN), 2.0, 2.1, 1.9, 2.05, 1000)]


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=EASTERN)


def test_one_minute_bars_fresh_for_60_seconds():
    assert is_cache_fresh("1m", TUESDAY_10AM, TUESDAY_10AM + timedelta(seconds=59)) is True
    assert is_cache_fresh("1m", TUESDAY_10AM, TUESDAY_10AM + timedelta(seconds=61)) is False


def test_five_minute_bars_fresh_for_300_seconds():
    assert is_cache_fresh("5m", TUESDAY_10AM, TUESDAY_10AM + timedelta(seconds=299)) is True
    assert is_cache_fresh("5m", TUESDAY_10AM, TUESDAY_10AM + timedelta(seconds=301)) is False


def test_daily_bars_stale_after_the_close():
    assert is_cache_fresh("daily", _at(20, 15, 30), _at(20, 16, 5)) is False
    assert is_cache_fresh("daily", _at(20, 16, 10), _at(20, 23, 0)) is True
    # Friday Oct 23 evening -> Monday Oct 26 morning: no close in between.
    assert is_cache_fresh("daily", _at(23, 17), _at(26, 10)) is True
    assert is_cache_fresh("daily", _at(23, 17), _at(26, 16, 1)) is False


def test_cached_bars_round_trip_with_timezones(db_conn):
    write_cached_bars(db_conn, "HOST", "1m", BarSeries(BARS, TUESDAY_10AM))

    cached = read_cached_bars(db_conn, "HOST", "1m")

    assert cached == BarSeries(BARS, TUESDAY_10AM)
    assert cached.bars[0].time.utcoffset() == timedelta(hours=-4)


def test_read_missing_cache_returns_none(db_conn):
    assert read_cached_bars(db_conn, "HOST", "daily") is None


def test_load_bars_uses_fresh_cache(db_conn):
    calls = []

    def fetch(ticker, interval):
        calls.append((ticker, interval))
        return BARS

    first = load_bars(db_conn, "HOST", "1m", TUESDAY_10AM, fetch)
    second = load_bars(db_conn, "HOST", "1m", TUESDAY_10AM + timedelta(seconds=30), fetch)

    assert calls == [("HOST", "1m")]
    assert first == second == BarSeries(BARS, TUESDAY_10AM)


def test_load_bars_refetches_stale_cache(db_conn):
    calls = []

    def fetch(ticker, interval):
        calls.append(ticker)
        return BARS

    load_bars(db_conn, "HOST", "1m", TUESDAY_10AM, fetch)
    refreshed = load_bars(db_conn, "HOST", "1m", TUESDAY_10AM + timedelta(minutes=2), fetch)

    assert len(calls) == 2
    assert refreshed.fetched_at == TUESDAY_10AM + timedelta(minutes=2)
