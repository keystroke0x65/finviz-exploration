"""Momentum ABCD (the day-trading form, not the harmonic AB=CD).

Long: price spikes to A, pulls back to B, bounces to a lower high C, then holds a
higher low D above B; the trade is the break of C with a stop under D.
Inverse ABCD mirrors it for shorts.
"""

from app.finviz_client import Bar, Interval
from app.market_time import EASTERN
from app.patterns.swings import Swing, find_swings
from app.patterns.types import DetectorContext, Direction, PatternMatch

ABCD_LOOKBACK_BARS = 60
MIN_SPIKE_PERCENT: dict[Interval, float] = {"1m": 3.0, "5m": 5.0}
MIN_RETRACE, MAX_RETRACE = 0.3, 0.7
IDEAL_RETRACE = 0.5
RETRACE_SCORE_WIDTH = 0.2
MAX_BEYOND_C_PERCENT = 2.0
INTRADAY: frozenset[Interval] = frozenset({"1m", "5m"})


def _average_volume(bars: list[Bar]) -> float:
    return sum(bar.volume for bar in bars) / len(bars) if bars else 0.0


def _match_abcd(bars: list[Bar], direction: Direction, timeframe: Interval) -> PatternMatch | None:
    # Today only: on 5m the lookback reaches into yesterday, where the overnight
    # gap would masquerade as the spike.
    today = bars[-1].time.astimezone(EASTERN).date()
    window = [bar for bar in bars[-ABCD_LOOKBACK_BARS:] if bar.time.astimezone(EASTERN).date() == today]
    swings = find_swings(window)
    is_long = direction == "long"
    sign = 1 if is_long else -1
    # Long: A is the top swing high; short: the bottom swing low.
    extremes = [swing for swing in swings if swing.is_high == is_long]
    counter_swings = [swing for swing in swings if swing.is_high != is_long]
    if not extremes:
        return None
    point_a: Swing = (max if is_long else min)(extremes, key=lambda swing: swing.price)
    before_a = window[: point_a.index]
    if not before_a:
        return None
    start_bar = min(before_a, key=lambda bar: bar.low) if is_long else max(before_a, key=lambda bar: bar.high)
    spike_start = start_bar.low if is_long else start_bar.high
    spike = (point_a.price - spike_start) * sign
    if spike <= 0 or spike / spike_start * 100 < MIN_SPIKE_PERCENT[timeframe]:
        return None
    # The spike must be the dominant move: otherwise the pullback of a bigger
    # opposite run would read as its own (much weaker) ABCD.
    earlier = window[: window.index(start_bar)]
    if earlier:
        prior_extreme = max(bar.high for bar in earlier) if is_long else min(bar.low for bar in earlier)
        if (prior_extreme - spike_start) * sign >= spike:
            return None

    after_a = [swing for swing in counter_swings if swing.index > point_a.index]
    if not after_a:
        return None
    point_b = (min if is_long else max)(after_a, key=lambda swing: swing.price)
    retrace = (point_a.price - point_b.price) * sign / spike
    if not (MIN_RETRACE <= retrace <= MAX_RETRACE):
        return None

    c_candidates = [
        swing for swing in extremes
        if swing.index > point_b.index and (point_a.price - swing.price) * sign > 0
        and (swing.price - point_b.price) * sign > 0
    ]
    if not c_candidates:
        return None
    point_c = c_candidates[-1]
    after_c = window[point_c.index + 1 :]
    if not after_c:
        return None
    point_d = min(bar.low for bar in after_c) if is_long else max(bar.high for bar in after_c)
    if (point_d - point_b.price) * sign <= 0:
        return None  # D undercut B: no higher low
    if (window[-1].close - point_c.price) * sign / point_c.price * 100 > MAX_BEYOND_C_PERCENT:
        return None

    spike_bars = window[: point_a.index + 1]
    pullback_bars = window[point_a.index + 1 : point_b.index + 1]
    parts = {
        "retrace": max(1 - abs(retrace - IDEAL_RETRACE) / RETRACE_SCORE_WIDTH, 0.0),
        "higher_low": min((point_d - point_b.price) * sign / ((point_c.price - point_b.price) * sign) * 2, 1.0),
        "volume": 1.0 if _average_volume(pullback_bars) < _average_volume(spike_bars) else 0.0,
    }
    d_bar = min(after_c, key=lambda bar: bar.low) if is_long else max(after_c, key=lambda bar: bar.high)
    return PatternMatch(
        pattern="abcd" if is_long else "inverse_abcd",
        direction=direction,
        timeframe=timeframe,
        entry=point_c.price,
        stop=point_d,
        detected_at=bars[-1].time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[
            (window[point_a.index].time, point_a.price),
            (window[point_b.index].time, point_b.price),
            (window[point_c.index].time, point_c.price),
            (d_bar.time, point_d),
        ],
    )


def detect_abcd(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    if context.timeframe not in INTRADAY:
        return []
    return [
        match
        for match in (_match_abcd(bars, "long", context.timeframe), _match_abcd(bars, "short", context.timeframe))
        if match is not None
    ]


ABCD_DETECTORS = [(detect_abcd, INTRADAY)]
