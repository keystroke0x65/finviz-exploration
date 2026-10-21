"""Bull and bear flags: a sharp pole followed by a shallow, tight consolidation."""

from app.finviz_client import Bar, Interval
from app.patterns.types import DetectorContext, Direction, PatternMatch

# A pole has to be a real move for its timeframe: small caps move 3% in
# minutes but 15% over several days is what a daily flag needs.
POLE_MIN_MOVE_PERCENT: dict[Interval, float] = {"1m": 3.0, "5m": 5.0, "daily": 15.0}
POLE_MAX_BARS: dict[Interval, int] = {"1m": 10, "5m": 8, "daily": 6}
MIN_FLAG_BARS = 3
MAX_FLAG_BARS = 12
MAX_RETRACE = 0.5
ALL_TIMEFRAMES: frozenset[Interval] = frozenset({"1m", "5m", "daily"})


def _average_volume(bars: list[Bar]) -> float:
    return sum(bar.volume for bar in bars) / len(bars)


def _match_flag(bars: list[Bar], flag_length: int, direction: Direction, timeframe: Interval) -> PatternMatch | None:
    flag = bars[-flag_length:]
    pole_end_index = len(bars) - flag_length - 1
    pole_window = bars[max(0, pole_end_index - POLE_MAX_BARS[timeframe]) : pole_end_index + 1]
    pole_end = bars[pole_end_index]
    flag_high = max(bar.high for bar in flag)
    flag_low = min(bar.low for bar in flag)

    if direction == "long":
        pole_start = min(pole_window[:-1], key=lambda bar: bar.low, default=None)
        if pole_start is None:
            return None
        pole_bottom, pole_top = pole_start.low, pole_end.high
        move_percent = (pole_top - pole_bottom) / pole_bottom * 100
        retrace = (pole_top - flag_low) / (pole_top - pole_bottom) if pole_top > pole_bottom else 1.0
        stays_inside_pole = flag_high <= pole_top
        entry, stop = flag_high, flag_low
    else:
        pole_start = max(pole_window[:-1], key=lambda bar: bar.high, default=None)
        if pole_start is None:
            return None
        pole_top, pole_bottom = pole_start.high, pole_end.low
        move_percent = (pole_top - pole_bottom) / pole_top * 100
        retrace = (flag_high - pole_bottom) / (pole_top - pole_bottom) if pole_top > pole_bottom else 1.0
        stays_inside_pole = flag_low >= pole_bottom
        entry, stop = flag_low, flag_high

    threshold = POLE_MIN_MOVE_PERCENT[timeframe]
    if move_percent < threshold or retrace > MAX_RETRACE or not stays_inside_pole or entry == stop:
        return None

    pole_bars = pole_window[pole_window.index(pole_start) :]
    parts = {
        "pole_strength": min(move_percent / threshold / 2, 1.0),
        "shallow_retrace": 1 - retrace / MAX_RETRACE,
        "volume_contraction": 1.0 if _average_volume(flag) < _average_volume(pole_bars) else 0.0,
    }
    return PatternMatch(
        pattern="bull_flag" if direction == "long" else "bear_flag",
        direction=direction,
        timeframe=timeframe,
        entry=entry,
        stop=stop,
        detected_at=bars[-1].time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[
            (pole_start.time, pole_bottom if direction == "long" else pole_top),
            (pole_end.time, pole_top if direction == "long" else pole_bottom),
            (flag[0].time, entry),
            (flag[-1].time, entry),
        ],
    )


def _best_flag(bars: list[Bar], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    candidates = [
        _match_flag(bars, flag_length, direction, timeframe)
        for flag_length in range(MIN_FLAG_BARS, MAX_FLAG_BARS + 1)
        if len(bars) >= flag_length + 2
    ]
    found = [match for match in candidates if match is not None]
    return max(found, key=lambda match: match.quality) if found else None


def detect_flags(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    return [
        match
        for match in (_best_flag(bars, "long", context.timeframe), _best_flag(bars, "short", context.timeframe))
        if match is not None
    ]


FLAG_DETECTORS = [(detect_flags, ALL_TIMEFRAMES)]
