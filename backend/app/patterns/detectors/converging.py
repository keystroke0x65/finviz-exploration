"""Converging patterns: pennants (after a pole), symmetrical triangles and wedges.

All three are judged from swing highs and lows: which way each side slopes, and
whether the two sides are closing in on each other.
"""

from app.finviz_client import Bar, Interval
from app.patterns.detectors.flags import POLE_MAX_BARS, POLE_MIN_MOVE_PERCENT
from app.patterns.swings import Swing, find_swings
from app.patterns.types import DetectorContext, Direction, PatternMatch

CONVERGING_LOOKBACK = 40
MIN_SWINGS_PER_SIDE = 2
MIN_CONSOLIDATION_BARS = 6
MAX_PENNANT_RETRACE = 0.5
# Pennant consolidations are short, so a 1-bar window finds their swings.
PENNANT_SWING_SIDE_BARS = 1
NEAR_EDGE_PERCENT = 2.0
MAX_SHORT_OF_ENTRY_PERCENT = 5.0
MAX_BEYOND_ENTRY_PERCENT = 2.0
# A wedge's sides must close in: the slower side's slope differs from the faster
# side's by at least this share of the faster slope.
MIN_CONVERGENCE = 0.2
FULL_SWING_SCORE = 4
ALL_TIMEFRAMES: frozenset[Interval] = frozenset({"1m", "5m", "daily"})


def _prices(swings: list[Swing]) -> list[float]:
    return [swing.price for swing in swings]


def _is_falling(prices: list[float]) -> bool:
    return len(prices) >= MIN_SWINGS_PER_SIDE and all(later < earlier for earlier, later in zip(prices, prices[1:]))


def _is_rising(prices: list[float]) -> bool:
    return len(prices) >= MIN_SWINGS_PER_SIDE and all(later > earlier for earlier, later in zip(prices, prices[1:]))


def _slope(swings: list[Swing]) -> float:
    first, last = swings[0], swings[-1]
    return (last.price - first.price) / first.price / max(last.index - first.index, 1)


def _is_relevant(close: float, entry: float, direction: Direction) -> bool:
    sign = 1 if direction == "long" else -1
    distance = (close - entry) * sign / entry * 100
    return -MAX_SHORT_OF_ENTRY_PERCENT <= distance <= MAX_BEYOND_ENTRY_PERCENT


def _contraction(window: list[Bar]) -> float:
    third = max(len(window) // 3, 1)
    first = max(bar.high for bar in window[:third]) - min(bar.low for bar in window[:third])
    last = max(bar.high for bar in window[-third:]) - min(bar.low for bar in window[-third:])
    return min(max(1 - last / first, 0.0), 1.0) if first > 0 else 0.0


def _match(pattern: str, direction: Direction, timeframe: Interval, bars: list[Bar], window: list[Bar],
           highs: list[Swing], lows: list[Swing], entry: float, stop: float) -> PatternMatch | None:
    if (entry - stop) * (1 if direction == "long" else -1) <= 0 or not _is_relevant(bars[-1].close, entry, direction):
        return None
    parts = {
        "touches": min((len(highs) + len(lows)) / (2 * FULL_SWING_SCORE), 1.0),
        "contraction": _contraction(window),
    }
    outline = sorted(highs + lows, key=lambda swing: swing.index)
    return PatternMatch(
        pattern=pattern,
        direction=direction,
        timeframe=timeframe,
        entry=entry,
        stop=stop,
        detected_at=bars[-1].time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[(window[swing.index].time, swing.price) for swing in outline],
    )


def _pennant(bars: list[Bar], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    window = bars[-CONVERGING_LOOKBACK:]
    is_long = direction == "long"
    top_index = max(range(len(window)), key=lambda i: window[i].high if is_long else -window[i].low)
    consolidation = window[top_index + 1 :]
    if len(consolidation) < MIN_CONSOLIDATION_BARS:
        return None
    pole_bars = window[max(0, top_index - POLE_MAX_BARS[timeframe]) : top_index + 1]
    pole_top = window[top_index].high if is_long else window[top_index].low
    pole_start = min(bar.low for bar in pole_bars) if is_long else max(bar.high for bar in pole_bars)
    pole = (pole_top - pole_start) * (1 if is_long else -1)
    if pole <= 0 or pole / pole_start * 100 < POLE_MIN_MOVE_PERCENT[timeframe]:
        return None

    swings = find_swings(consolidation, PENNANT_SWING_SIDE_BARS)
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]
    if not (_is_falling(_prices(highs)) and _is_rising(_prices(lows))):
        return None
    deepest = min(bar.low for bar in consolidation) if is_long else max(bar.high for bar in consolidation)
    if (pole_top - deepest) * (1 if is_long else -1) / pole > MAX_PENNANT_RETRACE:
        return None
    entry, stop = (highs[-1].price, lows[-1].price) if is_long else (lows[-1].price, highs[-1].price)
    return _match("bull_pennant" if is_long else "bear_pennant", direction, timeframe, bars, consolidation,
                  highs, lows, entry, stop)


def detect_pennants(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    if len(bars) < MIN_CONSOLIDATION_BARS + 2:
        return []
    found = [_pennant(bars, direction, context.timeframe) for direction in ("long", "short")]
    return [match for match in found if match is not None]


def _swing_sides(bars: list[Bar]) -> tuple[list[Bar], list[Swing], list[Swing]]:
    window = bars[-CONVERGING_LOOKBACK:]
    swings = find_swings(window)
    return window, [s for s in swings if s.is_high], [s for s in swings if not s.is_high]


def detect_symmetrical_triangles(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    window, highs, lows = _swing_sides(bars)
    lows = [low for low in lows if highs and low.index > highs[0].index]
    if not (_is_falling(_prices(highs)) and _is_rising(_prices(lows))):
        return []
    upper, lower = highs[-1].price, lows[-1].price
    close = bars[-1].close
    to_upper = (upper - close) / upper * 100
    to_lower = (close - lower) / lower * 100
    if to_upper <= NEAR_EDGE_PERCENT and to_upper <= to_lower:
        match = _match("symmetrical_triangle_up", "long", context.timeframe, bars, window, highs, lows, upper, lower)
    elif to_lower <= NEAR_EDGE_PERCENT:
        match = _match("symmetrical_triangle_down", "short", context.timeframe, bars, window, highs, lows, lower, upper)
    else:
        match = None
    return [match] if match else []


def detect_wedges(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    window, highs, lows = _swing_sides(bars)
    if len(highs) < MIN_SWINGS_PER_SIDE or len(lows) < MIN_SWINGS_PER_SIDE:
        return []
    high_slope, low_slope = _slope(highs), _slope(lows)
    if _is_falling(_prices(highs)) and _is_falling(_prices(lows)):
        # Falling wedge: lows fall more slowly than highs, so the sides converge.
        if (low_slope - high_slope) / abs(high_slope) < MIN_CONVERGENCE:
            return []
        match = _match("falling_wedge", "long", context.timeframe, bars, window, highs, lows,
                       highs[-1].price, lows[-1].price)
    elif _is_rising(_prices(highs)) and _is_rising(_prices(lows)):
        if (low_slope - high_slope) / abs(low_slope) < MIN_CONVERGENCE:
            return []
        match = _match("rising_wedge", "short", context.timeframe, bars, window, highs, lows,
                       lows[-1].price, highs[-1].price)
    else:
        match = None
    return [match] if match else []


CONVERGING_DETECTORS = [
    (detect_pennants, ALL_TIMEFRAMES),
    (detect_symmetrical_triangles, ALL_TIMEFRAMES),
    (detect_wedges, ALL_TIMEFRAMES),
]
