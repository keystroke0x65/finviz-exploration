"""Range breakouts/breakdowns and cup-and-handle patterns (and their inverted twins)."""

from app.finviz_client import Bar, Interval
from app.patterns.swings import find_swings
from app.patterns.types import DetectorContext, Direction, PatternMatch

ALL_TIMEFRAMES: frozenset[Interval] = frozenset({"1m", "5m", "daily"})

RANGE_LOOKBACK = 20
MAX_RANGE_PERCENT: dict[Interval, float] = {"1m": 3.0, "5m": 6.0, "daily": 15.0}
EDGE_ZONE = 0.15  # swings within this share of the range from an edge count as touches
MIN_EDGE_TOUCHES = 2
NEAR_EDGE_PERCENT = 2.0  # how far past an edge price may already be
NEAR_EDGE_SHARE = 0.25  # price must be in the outer quarter of the range on that side

CUP_LOOKBACK = 60
MIN_CUP_BARS = 20
HANDLE_BARS = (3, 10)
RIM_TOLERANCE = 0.03
MIN_CUP_DEPTH: dict[Interval, float] = {"1m": 0.03, "5m": 0.05, "daily": 0.10}
MAX_CUP_DEPTH = 0.50
MAX_HANDLE_SHARE_OF_DEPTH = 1 / 3
MAX_SHORT_OF_RIM_PERCENT = 5.0
MAX_BEYOND_RIM_PERCENT = 2.0


def detect_ranges(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    window = bars[-RANGE_LOOKBACK:]
    swings = find_swings(window)
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]
    if not highs or not lows:
        return []
    top, bottom = max(s.price for s in highs), min(s.price for s in lows)
    if top <= bottom or (top - bottom) / bottom * 100 > MAX_RANGE_PERCENT[context.timeframe]:
        return []
    zone = (top - bottom) * EDGE_ZONE
    top_touches = [s for s in highs if s.price >= top - zone]
    bottom_touches = [s for s in lows if s.price <= bottom + zone]
    if len(top_touches) < MIN_EDGE_TOUCHES or len(bottom_touches) < MIN_EDGE_TOUCHES:
        return []

    # "Near" is measured against the range height, not as a flat percent: in a tight range
    # a flat 2% covers the middle, which is no breakout. Just through an edge also counts.
    close = bars[-1].close
    near_band = (top - bottom) * NEAR_EDGE_SHARE
    beyond = NEAR_EDGE_PERCENT / 100
    if top - near_band <= close <= top * (1 + beyond):
        pattern, direction, entry, stop = "range_breakout", "long", top, bottom
    elif bottom * (1 - beyond) <= close <= bottom + near_band:
        pattern, direction, entry, stop = "range_breakdown", "short", bottom, top
    else:
        return []
    parts = {"touches": min((len(top_touches) + len(bottom_touches)) / 6, 1.0),
             "tightness": 1 - (top - bottom) / bottom * 100 / MAX_RANGE_PERCENT[context.timeframe]}
    outline = sorted(top_touches + bottom_touches, key=lambda swing: swing.index)
    return [PatternMatch(
        pattern=pattern, direction=direction, timeframe=context.timeframe, entry=entry, stop=stop,
        detected_at=bars[-1].time, quality=sum(parts.values()) / len(parts), quality_parts=parts,
        key_points=[(window[s.index].time, s.price) for s in outline],
    )]


def _extreme(bars: list[Bar], is_long: bool, rim: bool) -> float:
    """Rim (top for a cup) or bottom of a stretch of bars; mirrored for inverted cups."""
    if is_long == rim:
        return max(bar.high for bar in bars)
    return min(bar.low for bar in bars)


def _cup(bars: list[Bar], handle_length: int, direction: Direction, timeframe: Interval) -> PatternMatch | None:
    is_long = direction == "long"
    sign = 1 if is_long else -1
    window = bars[-CUP_LOOKBACK:]
    handle = window[-handle_length:]
    cup = window[:-handle_length]
    if len(cup) < MIN_CUP_BARS:
        return None
    quarter = len(cup) // 4
    left_rim = _extreme(cup[:quarter], is_long, rim=True)
    right_rim = _extreme(cup[-quarter:], is_long, rim=True)
    if abs(left_rim - right_rim) / max(left_rim, right_rim) > RIM_TOLERANCE:
        return None
    bottom_bar = (min if is_long else max)(cup, key=lambda bar: bar.low if is_long else bar.high)
    bottom_index = cup.index(bottom_bar)
    if not (quarter <= bottom_index <= len(cup) - quarter):
        return None  # a cup's low is in its middle, not at one side
    bottom = bottom_bar.low if is_long else bottom_bar.high
    rim = min(left_rim, right_rim) if is_long else max(left_rim, right_rim)
    depth = (rim - bottom) * sign
    if depth <= 0 or not (MIN_CUP_DEPTH[timeframe] <= depth / rim <= MAX_CUP_DEPTH):
        return None

    handle_extreme = _extreme(handle, is_long, rim=True)
    handle_floor = _extreme(handle, is_long, rim=False)
    if (handle_extreme - right_rim) * sign > 0:
        return None  # the "handle" already broke out above the rim
    if (right_rim - handle_floor) * sign > depth * MAX_HANDLE_SHARE_OF_DEPTH:
        return None  # handle too deep
    distance = (bars[-1].close - right_rim) * sign / right_rim * 100
    if not (-MAX_SHORT_OF_RIM_PERCENT <= distance <= MAX_BEYOND_RIM_PERCENT):
        return None

    parts = {
        "rim_symmetry": 1 - abs(left_rim - right_rim) / max(left_rim, right_rim) / RIM_TOLERANCE,
        "shallow_handle": 1 - (right_rim - handle_floor) * sign / (depth * MAX_HANDLE_SHARE_OF_DEPTH),
    }
    return PatternMatch(
        pattern="cup_and_handle" if is_long else "inverted_cup_and_handle",
        direction=direction, timeframe=timeframe, entry=right_rim, stop=handle_floor,
        detected_at=bars[-1].time, quality=sum(parts.values()) / len(parts), quality_parts=parts,
        key_points=[(cup[0].time, left_rim), (bottom_bar.time, bottom), (cup[-1].time, right_rim),
                    (handle[-1].time, handle_floor)],
    )


def detect_cups(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    found: list[PatternMatch] = []
    for direction in ("long", "short"):
        candidates = [
            _cup(bars, length, direction, context.timeframe)
            for length in range(HANDLE_BARS[0], HANDLE_BARS[1] + 1)
            if len(bars) >= MIN_CUP_BARS + length
        ]
        matches = [match for match in candidates if match is not None]
        if matches:
            found.append(max(matches, key=lambda match: match.quality))
    return found


RANGE_CUP_DETECTORS = [(detect_ranges, ALL_TIMEFRAMES), (detect_cups, ALL_TIMEFRAMES)]
