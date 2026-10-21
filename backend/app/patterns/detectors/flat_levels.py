"""Flat-top breakouts and flat-bottom breakdowns: price pressing a horizontal level
it has touched at least three times."""

from app.finviz_client import Bar, Interval
from app.patterns.types import DetectorContext, Direction, PatternMatch

FLAT_LOOKBACK_BARS = 30
FLAT_TOLERANCE_PERCENT = 0.5
MIN_FLAT_TOUCHES = 3
FULL_TOUCH_SCORE = 5
# Past the level by more than this, the breakout already happened.
MAX_BEYOND_LEVEL_PERCENT = 2.0
# Further than this from the level, price isn't pressing it.
MAX_SHORT_OF_LEVEL_PERCENT = 5.0
ALL_TIMEFRAMES: frozenset[Interval] = frozenset({"1m", "5m", "daily"})


def _match_flat(bars: list[Bar], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    window = bars[-FLAT_LOOKBACK_BARS:]
    extremes = [bar.high if direction == "long" else bar.low for bar in window]
    level = max(extremes) if direction == "long" else min(extremes)
    touch_indexes = [
        index for index, price in enumerate(extremes) if abs(price - level) / level * 100 <= FLAT_TOLERANCE_PERCENT
    ]
    if len(touch_indexes) < MIN_FLAT_TOUCHES:
        return None

    last_close = window[-1].close
    signed_distance = (last_close - level) / level * 100 * (1 if direction == "long" else -1)
    if not (-MAX_SHORT_OF_LEVEL_PERCENT <= signed_distance <= MAX_BEYOND_LEVEL_PERCENT):
        return None

    since_first_touch = window[touch_indexes[0] :]
    stop = min(bar.low for bar in since_first_touch) if direction == "long" else max(
        bar.high for bar in since_first_touch
    )
    if stop == level:
        return None
    touch_prices = [extremes[index] for index in touch_indexes]
    spread_percent = (max(touch_prices) - min(touch_prices)) / level * 100
    parts = {
        "touches": min(len(touch_indexes) / FULL_TOUCH_SCORE, 1.0),
        "tightness": 1 - spread_percent / FLAT_TOLERANCE_PERCENT,
    }
    return PatternMatch(
        pattern="flat_top_breakout" if direction == "long" else "flat_bottom_breakdown",
        direction=direction,
        timeframe=timeframe,
        entry=level,
        stop=stop,
        detected_at=bars[-1].time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[(window[index].time, extremes[index]) for index in touch_indexes],
    )


def detect_flat_levels(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    if len(bars) < MIN_FLAT_TOUCHES:
        return []
    return [
        match
        for match in (_match_flat(bars, "long", context.timeframe), _match_flat(bars, "short", context.timeframe))
        if match is not None
    ]


FLAT_LEVEL_DETECTORS = [(detect_flat_levels, ALL_TIMEFRAMES)]
