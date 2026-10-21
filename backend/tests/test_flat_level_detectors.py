from datetime import datetime, timedelta

import pytest

from app.finviz_client import Bar
from app.market_time import EASTERN
from app.patterns.detectors.flat_levels import detect_flat_levels
from app.patterns.types import DetectorContext

CONTEXT = DetectorContext(timeframe="5m", daily_levels=[], session=None, vwap=None)


def bars_from(highs: list[float], lows: list[float], last_close: float) -> list[Bar]:
    start = datetime(2026, 10, 20, 9, 30, tzinfo=EASTERN)
    bars = []
    for index, (high, low) in enumerate(zip(highs, lows)):
        close = (high + low) / 2
        bars.append(Bar(start + timedelta(minutes=5 * index), close, high, low, close, 1000))
    last = bars[-1]
    bars[-1] = Bar(last.time, last.open, max(last.high, last_close), last.low, last_close, last.volume)
    return bars


def test_flat_top_needs_three_touches():
    two_touches = [2.30, 2.50, 2.35, 2.32, 2.49, 2.40, 2.42]
    three_touches = [2.30, 2.50, 2.35, 2.32, 2.49, 2.40, 2.495, 2.44]
    lows = [2.20] * 10

    assert detect_flat_levels(bars_from(two_touches, lows[:7], 2.45), CONTEXT) == []
    [match] = detect_flat_levels(bars_from(three_touches, lows[:8], 2.46), CONTEXT)
    assert match.pattern == "flat_top_breakout"


def test_flat_top_entry_is_the_level_and_stop_below():
    highs = [2.30, 2.50, 2.35, 2.32, 2.49, 2.40, 2.495, 2.44]
    lows = [2.20, 2.40, 2.25, 2.22, 2.38, 2.30, 2.39, 2.36]

    [match] = detect_flat_levels(bars_from(highs, lows, 2.46), CONTEXT)

    assert match.direction == "long"
    assert match.entry == 2.50
    assert match.stop == pytest.approx(2.22)  # lowest low since the first touch
    assert match.quality_parts["touches"] == pytest.approx(3 / 5)


def test_flat_top_ignored_when_price_far_below():
    highs = [2.30, 2.50, 2.35, 2.32, 2.49, 2.40, 2.495, 2.10]
    lows = [2.20, 2.40, 2.25, 2.22, 2.38, 2.30, 2.39, 2.00]

    assert detect_flat_levels(bars_from(highs, lows, 2.05), CONTEXT) == []


def test_flat_bottom_breakdown_is_short():
    lows = [2.30, 2.10, 2.25, 2.28, 2.11, 2.20, 2.105, 2.15]
    highs = [2.40, 2.20, 2.35, 2.38, 2.22, 2.30, 2.21, 2.24]

    [match] = detect_flat_levels(bars_from(highs, lows, 2.14), CONTEXT)

    assert (match.pattern, match.direction) == ("flat_bottom_breakdown", "short")
    assert match.entry == 2.10
    assert match.stop > match.entry
