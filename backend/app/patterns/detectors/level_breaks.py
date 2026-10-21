"""Momentum breaks of key intraday levels: high/low of day, pre-market high/low,
opening range, previous close (red-to-green), and VWAP.

Each pattern is "relevant now" when price is just short of the level (forming)
or has just closed through it.
"""

from datetime import time

from app.finviz_client import Bar, Interval
from app.market_time import EASTERN
from app.patterns.types import DetectorContext, Direction, PatternMatch

RECENT_BARS = 3
NEAR_LEVEL_PERCENT = 2.0
STOP_LOOKBACK_BARS = 5
VOLUME_LOOKBACK_BARS = 20
MIN_BARS_BELOW_VWAP = 3

REGULAR_OPEN = time(9, 30)
OPENING_RANGE_END = time(9, 35)
REGULAR_CLOSE = time(16, 0)
INTRADAY: frozenset[Interval] = frozenset({"1m", "5m"})


def _eastern_time(bar: Bar) -> time:
    return bar.time.astimezone(EASTERN).time()


def _is_regular_session(bar: Bar) -> bool:
    return REGULAR_OPEN <= _eastern_time(bar) < REGULAR_CLOSE


def _volume_score(bars: list[Bar]) -> float:
    prior = bars[-VOLUME_LOOKBACK_BARS - 1 : -1]
    average = sum(bar.volume for bar in prior) / len(prior) if prior else 0
    if average == 0:
        return 0.0
    # Twice the recent average volume counts as full confirmation.
    return min(bars[-1].volume / average / 2, 1.0)


def _protective_stop(bars: list[Bar], direction: Direction) -> float:
    recent = bars[-STOP_LOOKBACK_BARS:]
    return min(bar.low for bar in recent) if direction == "long" else max(bar.high for bar in recent)


def _is_on_losing_side(stop: float, entry: float, direction: Direction) -> bool:
    return stop < entry if direction == "long" else stop > entry


def _proximity(bars: list[Bar], level: float, direction: Direction) -> float | None:
    """1.0 if price just closed through the level, a 0-1 closeness if just short of it, else None."""
    closes_through = [bar.close > level if direction == "long" else bar.close < level for bar in bars]
    was_before = not closes_through[-RECENT_BARS - 1]
    if was_before and any(closes_through[-RECENT_BARS:]):
        return 1.0
    last_close = bars[-1].close
    distance_percent = (level - last_close if direction == "long" else last_close - level) / level * 100
    if 0 <= distance_percent <= NEAR_LEVEL_PERCENT:
        return 1 - distance_percent / NEAR_LEVEL_PERCENT
    return None


def match_level_break(
    bars: list[Bar], level: float | None, direction: Direction, pattern: str, timeframe: Interval
) -> PatternMatch | None:
    if level is None or level <= 0 or len(bars) < STOP_LOOKBACK_BARS:
        return None
    proximity = _proximity(bars, level, direction)
    if proximity is None:
        return None
    stop = _protective_stop(bars, direction)
    if not _is_on_losing_side(stop, level, direction):
        return None
    parts = {"proximity": proximity, "volume": _volume_score(bars)}
    return PatternMatch(
        pattern=pattern,
        direction=direction,
        timeframe=timeframe,
        entry=level,
        stop=stop,
        detected_at=bars[-1].time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[(bars[-STOP_LOOKBACK_BARS].time, level), (bars[-1].time, level)],
    )


def _matches(*candidates: PatternMatch | None) -> list[PatternMatch]:
    return [match for match in candidates if match is not None]


def detect_day_extreme_breaks(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    if not bars or not _is_regular_session(bars[-1]):
        return []
    today = bars[-1].time.astimezone(EASTERN).date()
    todays_regular = [bar for bar in bars if bar.time.astimezone(EASTERN).date() == today and _is_regular_session(bar)]
    # The last few bars are excluded, or the current bar would always be the high.
    earlier = todays_regular[:-RECENT_BARS]
    if not earlier:
        return []
    return _matches(
        match_level_break(bars, max(bar.high for bar in earlier), "long", "high_of_day_break", context.timeframe),
        match_level_break(bars, min(bar.low for bar in earlier), "short", "low_of_day_break", context.timeframe),
    )


def detect_premarket_breaks(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    # The pre-market range is only final once the regular session has opened.
    if not bars or context.session is None or _eastern_time(bars[-1]) < REGULAR_OPEN:
        return []
    return _matches(
        match_level_break(bars, context.session.premarket_high, "long", "premarket_high_break", context.timeframe),
        match_level_break(bars, context.session.premarket_low, "short", "premarket_low_break", context.timeframe),
    )


def detect_opening_range_breaks(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    if not bars or context.session is None:
        return []
    last_time = _eastern_time(bars[-1])
    if not (OPENING_RANGE_END <= last_time < REGULAR_CLOSE):
        return []
    session = context.session
    return _matches(
        match_level_break(bars, session.opening_range_high, "long", "opening_range_breakout", context.timeframe),
        match_level_break(bars, session.opening_range_low, "short", "opening_range_breakdown", context.timeframe),
    )


def detect_previous_close_crosses(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    if not bars or context.session is None:
        return []
    previous_close = context.session.previous_close
    return _matches(
        match_level_break(bars, previous_close, "long", "red_to_green", context.timeframe),
        match_level_break(bars, previous_close, "short", "green_to_red", context.timeframe),
    )


def _vwap_cross(bars: list[Bar], vwap: list[float | None], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    window = list(zip(bars[-MIN_BARS_BELOW_VWAP - 1 :], vwap[-MIN_BARS_BELOW_VWAP - 1 :]))
    if any(value is None for _, value in window):
        return None
    *before, (last_bar, last_vwap) = window
    if direction == "long":
        crossed = all(bar.close < value for bar, value in before) and last_bar.close > last_vwap
    else:
        crossed = all(bar.close > value for bar, value in before) and last_bar.close < last_vwap
    if not crossed:
        return None
    entry = last_bar.high if direction == "long" else last_bar.low
    stop = _protective_stop(bars, direction)
    if not _is_on_losing_side(stop, entry, direction):
        return None
    strength = min(abs(last_bar.close - last_vwap) / last_vwap * 100, 1.0)
    parts = {"cross_strength": strength, "volume": _volume_score(bars)}
    return PatternMatch(
        pattern="vwap_reclaim" if direction == "long" else "vwap_rejection",
        direction=direction,
        timeframe=timeframe,
        entry=entry,
        stop=stop,
        detected_at=last_bar.time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[(bar.time, value) for bar, value in window],
    )


def detect_vwap_crosses(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    if context.vwap is None or len(bars) < max(MIN_BARS_BELOW_VWAP + 1, STOP_LOOKBACK_BARS):
        return []
    return _matches(
        _vwap_cross(bars, context.vwap, "long", context.timeframe),
        _vwap_cross(bars, context.vwap, "short", context.timeframe),
    )


LEVEL_BREAK_DETECTORS = [
    (detect_day_extreme_breaks, INTRADAY),
    (detect_premarket_breaks, INTRADAY),
    (detect_opening_range_breaks, INTRADAY),
    (detect_previous_close_crosses, INTRADAY),
    (detect_vwap_crosses, INTRADAY),
]
