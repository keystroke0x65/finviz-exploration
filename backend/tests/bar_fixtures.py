"""Helpers for building hand-made bar series in pattern tests."""

from datetime import date, datetime, timedelta

from app.finviz_client import Bar
from app.market_time import EASTERN

TRADING_DAY = date(2026, 10, 20)  # a Tuesday


def make_bar(hour: int, minute: int, open_price: float, high: float, low: float, close: float,
             volume: int = 1000, day: date = TRADING_DAY) -> Bar:
    return Bar(datetime(day.year, day.month, day.day, hour, minute, tzinfo=EASTERN),
               open_price, high, low, close, volume)


def minute_bars(start_hour: int, start_minute: int, closes: list[float], volume: int = 1000,
                spread: float = 0.01, day: date = TRADING_DAY, step_minutes: int = 1) -> list[Bar]:
    """Bars whose open is the previous close and whose high/low sit `spread` around them."""
    start = datetime(day.year, day.month, day.day, start_hour, start_minute, tzinfo=EASTERN)
    bars: list[Bar] = []
    previous_close = closes[0]
    for index, close in enumerate(closes):
        high = max(previous_close, close) + spread
        low = min(previous_close, close) - spread
        bars.append(Bar(start + timedelta(minutes=index * step_minutes), previous_close, high, low, close, volume))
        previous_close = close
    return bars


def daily_bars(closes: list[float], start: date = date(2024, 1, 2), spread: float = 0.05) -> list[Bar]:
    """One bar per weekday; high/low sit `spread` around open/close."""
    bars: list[Bar] = []
    day = start
    previous_close = closes[0]
    for close in closes:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        bars.append(Bar(datetime(day.year, day.month, day.day, tzinfo=EASTERN), previous_close,
                        max(previous_close, close) + spread, min(previous_close, close) - spread, close, 100_000))
        previous_close = close
        day += timedelta(days=1)
    return bars
