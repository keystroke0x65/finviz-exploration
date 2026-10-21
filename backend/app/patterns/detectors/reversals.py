"""Reversal patterns (5m and daily): head and shoulders, triple tops/bottoms, and
rounding tops/bottoms, plus their mirror images."""

from app.finviz_client import Bar, Interval
from app.patterns.swings import Swing, find_swings
from app.patterns.types import DetectorContext, Direction, PatternMatch

REVERSAL_TIMEFRAMES: frozenset[Interval] = frozenset({"5m", "daily"})
REVERSAL_LOOKBACK = 60

SHOULDER_TOLERANCE = 0.03
MIN_HEAD_PROMINENCE = 0.01
NEAR_NECKLINE_PERCENT = 3.0
BEYOND_NECKLINE_PERCENT = 2.0

TRIPLE_TOLERANCE = 0.02
MIN_TEST_SEPARATION = 5
MAX_SHORT_OF_NECKLINE_PERCENT = 5.0

ROUNDING_BARS = 30
MIN_ROUNDING_DEPTH: dict[Interval, float] = {"1m": 0.02, "5m": 0.03, "daily": 0.10}
MAX_AGAINST_TREND_SHARE = 0.25
MAX_SHORT_OF_RIM_PERCENT = 5.0
MAX_BEYOND_RIM_PERCENT = 2.0


def _near_neckline(close: float, neckline: float, direction: Direction, short_of: float) -> bool:
    sign = 1 if direction == "long" else -1
    distance = (close - neckline) * sign / neckline * 100
    return -short_of <= distance <= BEYOND_NECKLINE_PERCENT


def _build(pattern: str, direction: Direction, timeframe: Interval, bars: list[Bar], entry: float, stop: float,
           parts: dict[str, float], points: list[tuple]) -> PatternMatch | None:
    if (entry - stop) * (1 if direction == "long" else -1) <= 0:
        return None
    return PatternMatch(
        pattern=pattern, direction=direction, timeframe=timeframe, entry=entry, stop=stop,
        detected_at=bars[-1].time, quality=sum(parts.values()) / len(parts), quality_parts=parts,
        key_points=points,
    )


def _head_and_shoulders(bars: list[Bar], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    # direction is the trade: short for a (top) head and shoulders, long for the inverse.
    is_top = direction == "short"
    window = bars[-REVERSAL_LOOKBACK:]
    swings = find_swings(window)
    peaks = [s for s in swings if s.is_high == is_top]
    troughs = [s for s in swings if s.is_high != is_top]
    if len(peaks) < 3:
        return None
    left, head, right = peaks[-3:]
    more_extreme = (lambda a, b: a > b) if is_top else (lambda a, b: a < b)
    shoulder = max(left.price, right.price) if is_top else min(left.price, right.price)
    if not more_extreme(head.price, shoulder * (1 + MIN_HEAD_PROMINENCE if is_top else 1 - MIN_HEAD_PROMINENCE)):
        return None
    if abs(left.price - right.price) / max(left.price, right.price) > SHOULDER_TOLERANCE:
        return None
    left_trough = [t for t in troughs if left.index < t.index < head.index]
    right_trough = [t for t in troughs if head.index < t.index < right.index]
    if not left_trough or not right_trough:
        return None
    lows = [left_trough[-1].price, right_trough[0].price]
    neckline = max(lows) if is_top else min(lows)
    if not _near_neckline(bars[-1].close, neckline, direction, NEAR_NECKLINE_PERCENT):
        return None
    parts = {
        "symmetry": 1 - abs(left.price - right.price) / max(left.price, right.price) / SHOULDER_TOLERANCE,
        "head_prominence": min(abs(head.price - shoulder) / shoulder / (MIN_HEAD_PROMINENCE * 5), 1.0),
    }
    points = [(window[s.index].time, s.price) for s in (left, left_trough[-1], head, right_trough[0], right)]
    return _build("head_and_shoulders" if is_top else "inverse_head_and_shoulders", direction, timeframe, bars,
                  neckline, right.price, parts, points)


def detect_head_and_shoulders(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    found = [_head_and_shoulders(bars, direction, context.timeframe) for direction in ("short", "long")]
    return [match for match in found if match is not None]


def _triple(bars: list[Bar], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    is_bottom = direction == "long"
    window = bars[-REVERSAL_LOOKBACK:]
    swings = find_swings(window)
    tests = [s for s in swings if s.is_high != is_bottom]
    if len(tests) < 3:
        return None
    first, second, third = tests[-3:]
    if second.index - first.index < MIN_TEST_SEPARATION or third.index - second.index < MIN_TEST_SEPARATION:
        return None
    prices = [first.price, second.price, third.price]
    if (max(prices) - min(prices)) / min(prices) > TRIPLE_TOLERANCE:
        return None
    before_first = window[: first.index]
    if is_bottom and any(bar.low < first.price for bar in before_first):
        return None
    if not is_bottom and any(bar.high > first.price for bar in before_first):
        return None
    necklines = [s for s in swings if s.is_high == is_bottom and first.index < s.index < third.index]
    if len(necklines) < 2:
        return None
    neckline = max(s.price for s in necklines) if is_bottom else min(s.price for s in necklines)
    if not _near_neckline(bars[-1].close, neckline, direction, MAX_SHORT_OF_NECKLINE_PERCENT):
        return None
    stop = min(prices) if is_bottom else max(prices)
    parts = {"symmetry": 1 - (max(prices) - min(prices)) / min(prices) / TRIPLE_TOLERANCE}
    points = [(window[s.index].time, s.price) for s in sorted([first, second, third, *necklines], key=lambda s: s.index)]
    return _build("triple_bottom" if is_bottom else "triple_top", direction, timeframe, bars, neckline, stop,
                  parts, points)


def detect_triples(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    found = [_triple(bars, direction, context.timeframe) for direction in ("long", "short")]
    return [match for match in found if match is not None]


def _share_against(closes: list[float], expected_sign: int) -> float:
    steps = [later - earlier for earlier, later in zip(closes, closes[1:])]
    return sum(1 for step in steps if step * expected_sign < 0) / len(steps) if steps else 1.0


def _rounding(bars: list[Bar], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    is_bottom = direction == "long"
    sign = 1 if is_bottom else -1
    window = bars[-ROUNDING_BARS:]
    if len(window) < ROUNDING_BARS:
        return None
    closes = [bar.close for bar in window]
    bottom_index = (min if is_bottom else max)(range(len(closes)), key=lambda i: closes[i])
    third = len(closes) // 3
    if not (third <= bottom_index < len(closes) - third):
        return None
    depth = MIN_ROUNDING_DEPTH[timeframe]
    bottom_close = closes[bottom_index]
    for end in (closes[0], closes[-1]):
        if (end - bottom_close) * sign / bottom_close < depth:
            return None
    falling, rising = closes[: bottom_index + 1], closes[bottom_index:]
    if _share_against(falling, -sign) > MAX_AGAINST_TREND_SHARE or _share_against(rising, sign) > MAX_AGAINST_TREND_SHARE:
        return None
    rim = max(bar.high for bar in window[:3]) if is_bottom else min(bar.low for bar in window[:3])
    stop = min(bar.low for bar in window) if is_bottom else max(bar.high for bar in window)
    distance = (closes[-1] - rim) * sign / rim * 100
    if not (-MAX_SHORT_OF_RIM_PERCENT <= distance <= MAX_BEYOND_RIM_PERCENT):
        return None
    parts = {"smoothness": 1 - max(_share_against(falling, -sign), _share_against(rising, sign)) / MAX_AGAINST_TREND_SHARE}
    points = [(window[0].time, rim), (window[bottom_index].time, stop), (window[-1].time, closes[-1])]
    return _build("rounding_bottom" if is_bottom else "rounding_top", direction, timeframe, bars, rim, stop,
                  parts, points)


def detect_rounding(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    found = [_rounding(bars, direction, context.timeframe) for direction in ("long", "short")]
    return [match for match in found if match is not None]


REVERSAL_DETECTORS = [
    (detect_head_and_shoulders, REVERSAL_TIMEFRAMES),
    (detect_triples, REVERSAL_TIMEFRAMES),
    (detect_rounding, REVERSAL_TIMEFRAMES),
]
