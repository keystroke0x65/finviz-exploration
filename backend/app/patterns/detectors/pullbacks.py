"""Micro pullbacks (a 1-2 bar dip inside a strong run) and the first pullback of the
day after a gap (first bounce fail after a gap down)."""

from datetime import time

from app.finviz_client import Bar, Interval
from app.market_time import EASTERN
from app.patterns.types import DetectorContext, Direction, PatternMatch

INTRADAY: frozenset[Interval] = frozenset({"1m", "5m"})

MIN_RUN_BARS = 3
MIN_RUN_GAIN_PERCENT: dict[Interval, float] = {"1m": 2.0, "5m": 3.0}
MAX_MICRO_RETRACE = 0.4
MAX_MICRO_PULLBACK_BARS = 2

GAP_PERCENT = 4.0
FULL_GAP_SCORE_PERCENT = 8.0
MIN_PUSH_PERCENT = 2.0
MIN_FIRST_PULLBACK_BARS = 2
MAX_FIRST_PULLBACK_RETRACE = 0.6
REGULAR_OPEN = time(9, 30)


def _eastern_day(bar: Bar):
    return bar.time.astimezone(EASTERN).date()


def _average_volume(bars: list[Bar]) -> float:
    return sum(bar.volume for bar in bars) / len(bars) if bars else 0.0


def _micro_pullback(bars: list[Bar], pullback_length: int, timeframe: Interval) -> PatternMatch | None:
    pullback = bars[-pullback_length:]
    before = bars[:-pullback_length]
    run_end = len(before) - 1
    run_start = run_end
    # The run stops at the overnight boundary: yesterday's close to today's
    # first print is a gap, not part of a run.
    while (
        run_start > 0
        and before[run_start].close > before[run_start - 1].close
        and _eastern_day(before[run_start]) == _eastern_day(before[run_start - 1])
    ):
        run_start -= 1
    run = before[run_start : run_end + 1]
    if len(run) < MIN_RUN_BARS:
        return None
    if pullback[0].close >= run[-1].close:
        return None  # not a dip
    top = max(bar.high for bar in run)
    base = min(bar.low for bar in run)
    if any(bar.high > top for bar in pullback):
        return None  # a new high is a breakout, not a pullback
    gain_percent = (top - base) / base * 100
    threshold = MIN_RUN_GAIN_PERCENT[timeframe]
    if gain_percent < threshold:
        return None
    entry = max(bar.high for bar in pullback)
    stop = min(bar.low for bar in pullback)
    retrace = (top - stop) / (top - base)
    if retrace > MAX_MICRO_RETRACE or entry <= stop:
        return None
    parts = {
        "run_strength": min(gain_percent / threshold / 2, 1.0),
        "shallow": 1 - retrace / MAX_MICRO_RETRACE,
        "volume_drop": 1.0 if _average_volume(pullback) < _average_volume(run) else 0.0,
    }
    return PatternMatch(
        pattern="micro_pullback",
        direction="long",
        timeframe=timeframe,
        entry=entry,
        stop=stop,
        detected_at=bars[-1].time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[(run[0].time, base), (run[-1].time, top), (pullback[-1].time, stop)],
    )


def detect_micro_pullbacks(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    candidates = [
        _micro_pullback(bars, length, context.timeframe)
        for length in range(1, MAX_MICRO_PULLBACK_BARS + 1)
        if len(bars) >= MIN_RUN_BARS + length
    ]
    found = [match for match in candidates if match is not None]
    return [max(found, key=lambda match: match.quality)] if found else []


def _first_pullback_span(today: list[Bar], direction: Direction) -> tuple[int, int, int] | None:
    """(extreme index, first pullback bar, last pullback bar) of the day's first pullback."""
    sign = 1 if direction == "long" else -1
    extreme = today[0].high if direction == "long" else today[0].low
    for index in range(1, len(today) - MIN_FIRST_PULLBACK_BARS + 1):
        bar_extreme = today[index].high if direction == "long" else today[index].low
        if (bar_extreme - extreme) * sign > 0:
            extreme = bar_extreme
            continue
        previous = today[index - 1]
        made_new_extreme = (previous.high if direction == "long" else previous.low) == extreme
        if not made_new_extreme:
            continue
        end = index
        while end + 1 < len(today) and _is_pullback_bar(today[end + 1], today[end], direction):
            end += 1
        # A one-bar dip isn't a pullback, so the search carries on past it.
        if end - index + 1 >= MIN_FIRST_PULLBACK_BARS and _is_pullback_bar(today[index], previous, direction):
            return index - 1, index, end
    return None


def _is_pullback_bar(bar: Bar, previous: Bar, direction: Direction) -> bool:
    return bar.high < previous.high if direction == "long" else bar.low > previous.low


def _current_session_bars(bars: list[Bar]) -> list[Bar]:
    """Today's bars from the regular open once it has happened, else today's pre-market.

    The 9:30 open is the gap a momentum trader trades; pre-market prints and dips
    before it would otherwise set the "open" and use up the "first" pullback.
    """
    last = bars[-1].time.astimezone(EASTERN)
    today = [bar for bar in bars if bar.time.astimezone(EASTERN).date() == last.date()]
    if last.time() < REGULAR_OPEN:
        return today
    return [bar for bar in today if bar.time.astimezone(EASTERN).time() >= REGULAR_OPEN]


def _first_pullback(bars: list[Bar], context: DetectorContext, direction: Direction) -> PatternMatch | None:
    previous_close = context.session.previous_close if context.session else None
    if previous_close is None or not bars:
        return None
    today = _current_session_bars(bars)
    if len(today) < MIN_FIRST_PULLBACK_BARS + 2:
        return None
    sign = 1 if direction == "long" else -1
    open_price = today[0].open
    gap_percent = (open_price - previous_close) * sign / previous_close * 100
    if gap_percent < GAP_PERCENT:
        return None

    span = _first_pullback_span(today, direction)
    if span is None:
        return None
    extreme_index, first, last = span
    extreme = today[extreme_index].high if direction == "long" else today[extreme_index].low
    if (extreme - open_price) * sign / open_price * 100 < MIN_PUSH_PERCENT:
        return None
    is_ongoing = last == len(today) - 1
    just_broke = last == len(today) - 2 and not _is_pullback_bar(today[-1], today[last], direction)
    if not (is_ongoing or just_broke):
        return None  # the first pullback already played out

    pullback = today[first : last + 1]
    entry = today[last].high if direction == "long" else today[last].low
    stop = min(bar.low for bar in pullback) if direction == "long" else max(bar.high for bar in pullback)
    retrace = (extreme - stop) * sign / ((extreme - open_price) * sign)
    if retrace > MAX_FIRST_PULLBACK_RETRACE or (entry - stop) * sign <= 0:
        return None
    parts = {
        "gap": min(gap_percent / FULL_GAP_SCORE_PERCENT, 1.0),
        "shallow": 1 - retrace / MAX_FIRST_PULLBACK_RETRACE,
        "volume_drop": 1.0 if _average_volume(pullback) < _average_volume(today[: extreme_index + 1]) else 0.0,
    }
    return PatternMatch(
        pattern="first_pullback" if direction == "long" else "first_bounce_fail",
        direction=direction,
        timeframe=context.timeframe,
        entry=entry,
        stop=stop,
        detected_at=bars[-1].time,
        quality=sum(parts.values()) / len(parts),
        quality_parts=parts,
        key_points=[(today[0].time, open_price), (today[extreme_index].time, extreme), (today[last].time, stop)],
    )


def detect_first_pullbacks(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    return [
        match
        for match in (_first_pullback(bars, context, "long"), _first_pullback(bars, context, "short"))
        if match is not None
    ]


PULLBACK_DETECTORS = [(detect_micro_pullbacks, INTRADAY), (detect_first_pullbacks, INTRADAY)]
