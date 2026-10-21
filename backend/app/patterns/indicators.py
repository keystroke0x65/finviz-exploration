from datetime import date, time

from app.finviz_client import Bar
from app.market_time import EASTERN
from app.patterns.types import SessionLevels

PREMARKET_OPEN = time(4, 0)
REGULAR_OPEN = time(9, 30)
OPENING_RANGE_END = time(9, 35)
REGULAR_CLOSE = time(16, 0)


def _eastern_date(bar: Bar) -> date:
    return bar.time.astimezone(EASTERN).date()


def _eastern_time(bar: Bar) -> time:
    return bar.time.astimezone(EASTERN).time()


def session_vwap(bars: list[Bar]) -> list[float | None]:
    """Volume-weighted average price, anchored at the 04:00 ET pre-market open each day."""
    vwap: list[float | None] = []
    current_day: date | None = None
    price_volume_total = 0.0
    volume_total = 0
    for bar in bars:
        if _eastern_time(bar) < PREMARKET_OPEN:
            vwap.append(None)
            continue
        if _eastern_date(bar) != current_day:
            current_day, price_volume_total, volume_total = _eastern_date(bar), 0.0, 0
        typical_price = (bar.high + bar.low + bar.close) / 3
        price_volume_total += typical_price * bar.volume
        volume_total += bar.volume
        vwap.append(price_volume_total / volume_total if volume_total else None)
    return vwap


def _high_low(bars: list[Bar]) -> tuple[float | None, float | None]:
    if not bars:
        return None, None
    return max(bar.high for bar in bars), min(bar.low for bar in bars)


def session_levels(intraday_bars: list[Bar], daily_bars: list[Bar], today: date) -> SessionLevels:
    todays_bars = [bar for bar in intraday_bars if _eastern_date(bar) == today]
    premarket = [bar for bar in todays_bars if PREMARKET_OPEN <= _eastern_time(bar) < REGULAR_OPEN]
    regular = [bar for bar in todays_bars if REGULAR_OPEN <= _eastern_time(bar) < REGULAR_CLOSE]
    opening_range = [bar for bar in regular if _eastern_time(bar) < OPENING_RANGE_END]
    earlier_days = [bar for bar in daily_bars if _eastern_date(bar) < today]

    premarket_high, premarket_low = _high_low(premarket)
    day_high, day_low = _high_low(regular)
    opening_range_high, opening_range_low = _high_low(opening_range)
    return SessionLevels(
        premarket_high=premarket_high,
        premarket_low=premarket_low,
        day_high=day_high,
        day_low=day_low,
        opening_range_high=opening_range_high,
        opening_range_low=opening_range_low,
        previous_close=earlier_days[-1].close if earlier_days else None,
    )
