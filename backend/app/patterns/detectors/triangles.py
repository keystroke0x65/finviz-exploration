"""Ascending triangles (flat top, rising lows) and descending triangles (flat bottom,
falling highs): buyers or sellers pressing a level while the other side gives ground."""

from app.finviz_client import Bar, Interval
from app.patterns.swings import Swing, find_swings
from app.patterns.types import DetectorContext, Direction, PatternMatch

TRIANGLE_LOOKBACK_BARS = 40
FLAT_TOLERANCE_PERCENT = 0.75
MIN_RISE_PERCENT = 0.3
MIN_FLAT_TOUCHES = 2
MIN_SLOPING_SWINGS = 2
FULL_TOUCH_SCORE = 4
FULL_SLOPE_SCORE = 3
MAX_SHORT_OF_LEVEL_PERCENT = 5.0
MAX_BEYOND_LEVEL_PERCENT = 2.0
ALL_TIMEFRAMES: frozenset[Interval] = frozenset({"1m", "5m", "daily"})


def _range(bars: list[Bar]) -> float:
    return max(bar.high for bar in bars) - min(bar.low for bar in bars)


def _contraction(window: list[Bar]) -> float:
    third = max(len(window) // 3, 1)
    first, last = _range(window[:third]), _range(window[-third:])
    if first <= 0:
        return 0.0
    return min(max(1 - last / first, 0.0), 1.0)


def _is_steadily_moving(prices: list[float], direction: Direction) -> bool:
    sign = 1 if direction == "long" else -1
    return all(
        (later - earlier) * sign / earlier * 100 >= MIN_RISE_PERCENT for earlier, later in zip(prices, prices[1:])
    )


def _match_triangle(bars: list[Bar], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    window = bars[-TRIANGLE_LOOKBACK_BARS:]
    swings = find_swings(window)
    # Long: the flat side is the swing highs and the sloping side the lows.
    flat_side = [swing for swing in swings if swing.is_high == (direction == "long")]
    sloping_side = [swing for swing in swings if swing.is_high != (direction == "long")]
    if len(flat_side) < MIN_FLAT_TOUCHES:
        return None

    level = max(s.price for s in flat_side) if direction == "long" else min(s.price for s in flat_side)
    touches = [s for s in flat_side if abs(s.price - level) / level * 100 <= FLAT_TOLERANCE_PERCENT]
    if len(touches) < MIN_FLAT_TOUCHES:
        return None
    slope_swings: list[Swing] = [s for s in sloping_side if s.index > touches[0].index]
    if len(slope_swings) < MIN_SLOPING_SWINGS or not _is_steadily_moving([s.price for s in slope_swings], direction):
        return None

    last_close = window[-1].close
    signed_distance = (last_close - level) / level * 100 * (1 if direction == "long" else -1)
    if not (-MAX_SHORT_OF_LEVEL_PERCENT <= signed_distance <= MAX_BEYOND_LEVEL_PERCENT):
        return None

    stop = slope_swings[-1].price
    parts = {
        "touches": min(len(touches) / FULL_TOUCH_SCORE, 1.0),
        "sloping_side": min(len(slope_swings) / FULL_SLOPE_SCORE, 1.0),
        "contraction": _contraction(window),
    }
    outline = sorted(touches + slope_swings, key=lambda swing: swing.index)
    return PatternMatch(
        pattern="ascending_triangle" if direction == "long" else "descending_triangle",
        direction=direction,
        timeframe=timeframe,
        entry=level,
        stop=stop,
        detected_at=bars[-1].time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[(window[swing.index].time, swing.price) for swing in outline],
    )


def detect_triangles(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    return [
        match
        for match in (_match_triangle(bars, "long", context.timeframe), _match_triangle(bars, "short", context.timeframe))
        if match is not None
    ]


TRIANGLE_DETECTORS = [(detect_triangles, ALL_TIMEFRAMES)]
