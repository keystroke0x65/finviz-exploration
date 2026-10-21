"""Double bottoms and double tops: two tests of the same price with a real swing
between them; the trade is the break of that swing (the neckline)."""

from app.finviz_client import Bar, Interval
from app.patterns.swings import find_swings
from app.patterns.types import DetectorContext, Direction, PatternMatch

DOUBLE_LOOKBACK_BARS = 60
MATCH_TOLERANCE_PERCENT = 2.0
MIN_SEPARATION_BARS = 5
MIN_DEPTH_PERCENT: dict[Interval, float] = {"1m": 1.5, "5m": 2.5, "daily": 8.0}
MAX_SHORT_OF_NECKLINE_PERCENT = 5.0
RECENT_BARS = 3
ALL_TIMEFRAMES: frozenset[Interval] = frozenset({"1m", "5m", "daily"})


def _is_relevant(window: list[Bar], neckline: float, direction: Direction) -> bool:
    sign = 1 if direction == "long" else -1
    was_short_before = len(window) > RECENT_BARS and (window[-RECENT_BARS - 1].close - neckline) * sign <= 0
    if was_short_before and any((bar.close - neckline) * sign > 0 for bar in window[-RECENT_BARS:]):
        return True  # just broke the neckline
    shortfall = (neckline - window[-1].close) * sign / neckline * 100
    return 0 <= shortfall <= MAX_SHORT_OF_NECKLINE_PERCENT


def _match_double(bars: list[Bar], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    window = bars[-DOUBLE_LOOKBACK_BARS:]
    swings = find_swings(window)
    # Long: the two tests are swing lows and the neckline is a swing high.
    tests = [swing for swing in swings if swing.is_high == (direction == "short")]
    if len(tests) < 2:
        return None
    first, second = tests[-2], tests[-1]
    if second.index - first.index < MIN_SEPARATION_BARS:
        return None
    if abs(first.price - second.price) / first.price * 100 > MATCH_TOLERANCE_PERCENT:
        return None
    # A double bottom is the low of the move: nothing lower before the first
    # test. Without this, a tight range at the top of a run matches too.
    before_first = window[: first.index]
    if direction == "long" and any(bar.low < first.price for bar in before_first):
        return None
    if direction == "short" and any(bar.high > first.price for bar in before_first):
        return None
    necklines = [
        swing for swing in swings
        if swing.is_high == (direction == "long") and first.index < swing.index < second.index
    ]
    if not necklines:
        return None
    neckline = (max if direction == "long" else min)(necklines, key=lambda swing: swing.price)

    inner_test = max(first.price, second.price) if direction == "long" else min(first.price, second.price)
    depth_percent = abs(neckline.price - inner_test) / inner_test * 100
    threshold = MIN_DEPTH_PERCENT[timeframe]
    if depth_percent < threshold or not _is_relevant(window, neckline.price, direction):
        return None

    stop = min(first.price, second.price) if direction == "long" else max(first.price, second.price)
    parts = {
        "symmetry": max(1 - abs(first.price - second.price) / first.price * 100 / MATCH_TOLERANCE_PERCENT, 0.0),
        "depth": min(depth_percent / threshold / 2, 1.0),
        "volume_on_retest": 1.0 if window[second.index].volume < window[first.index].volume else 0.0,
    }
    return PatternMatch(
        pattern="double_bottom" if direction == "long" else "double_top",
        direction=direction,
        timeframe=timeframe,
        entry=neckline.price,
        stop=stop,
        detected_at=bars[-1].time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[(window[swing.index].time, swing.price) for swing in (first, neckline, second)],
    )


def detect_doubles(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    return [
        match
        for match in (_match_double(bars, "long", context.timeframe), _match_double(bars, "short", context.timeframe))
        if match is not None
    ]


DOUBLE_DETECTORS = [(detect_doubles, ALL_TIMEFRAMES)]
