import pytest

from app.patterns.detectors import run_detectors
from app.patterns.detectors.level_breaks import (
    detect_day_extreme_breaks,
    detect_opening_range_breaks,
    detect_premarket_breaks,
    detect_previous_close_crosses,
    detect_vwap_crosses,
)
from app.patterns.indicators import session_levels, session_vwap
from app.patterns.types import DetectorContext
from tests.bar_fixtures import TRADING_DAY, make_bar, minute_bars

HOD_CLOSES = [2.0, 2.1, 2.2, 2.3, 2.4, 2.45, 2.4, 2.35, 2.3, 2.35, 2.4]


def context_for(bars, previous_close=None, timeframe="1m"):
    levels = session_levels(bars, [], TRADING_DAY)
    if previous_close is not None:
        levels = levels.__class__(**{**levels.__dict__, "previous_close": previous_close})
    return DetectorContext(timeframe=timeframe, daily_levels=[], session=levels, vwap=session_vwap(bars))


def names(matches):
    return {match.pattern for match in matches}


def test_high_of_day_break_detects_close_through_prior_high():
    bars = minute_bars(9, 30, HOD_CLOSES + [2.44, 2.47, 2.52])

    [match] = [m for m in detect_day_extreme_breaks(bars, context_for(bars)) if m.pattern == "high_of_day_break"]

    assert match.direction == "long"
    assert match.entry == pytest.approx(2.46)  # the 2.45 bar's high, before the last 3 bars
    assert match.stop == pytest.approx(2.29)  # lowest low of the last 5 bars
    assert match.detected_at == bars[-1].time
    assert match.quality_parts["proximity"] == 1.0


def test_high_of_day_break_forming_just_below_level():
    bars = minute_bars(9, 30, HOD_CLOSES + [2.42, 2.43, 2.44])

    [match] = [m for m in detect_day_extreme_breaks(bars, context_for(bars)) if m.pattern == "high_of_day_break"]

    assert match.entry == pytest.approx(2.46)
    assert 0 < match.quality_parts["proximity"] < 1


def test_high_of_day_break_ignored_when_far_below():
    bars = minute_bars(9, 30, HOD_CLOSES + [2.3, 2.28, 2.3])

    assert "high_of_day_break" not in names(detect_day_extreme_breaks(bars, context_for(bars)))


def test_high_of_day_break_only_during_regular_hours():
    bars = minute_bars(8, 0, HOD_CLOSES + [2.44, 2.47, 2.52])

    assert detect_day_extreme_breaks(bars, context_for(bars)) == []


def test_premarket_high_break_not_detected_before_open():
    bars = minute_bars(8, 0, HOD_CLOSES + [2.44, 2.47, 2.52])

    assert detect_premarket_breaks(bars, context_for(bars)) == []


def test_premarket_high_break_after_open():
    premarket = minute_bars(9, 0, [2.0, 2.2, 2.4, 2.3])  # pre-market high 2.41
    regular = minute_bars(9, 30, [2.3, 2.32, 2.35, 2.38, 2.39, 2.44])
    bars = premarket + regular

    [match] = [m for m in detect_premarket_breaks(bars, context_for(bars)) if m.direction == "long"]

    assert match.pattern == "premarket_high_break"
    assert match.entry == pytest.approx(2.41)


def test_opening_range_breakout_needs_range_complete():
    bars = minute_bars(9, 30, [2.0, 2.1, 2.05, 2.2])  # last bar 09:33

    assert detect_opening_range_breaks(bars, context_for(bars)) == []


def test_opening_range_breakout_after_range():
    bars = minute_bars(9, 30, [2.0, 2.1, 2.05, 2.08, 2.06, 2.07, 2.09, 2.15])  # range high 2.11

    [match] = [m for m in detect_opening_range_breaks(bars, context_for(bars)) if m.direction == "long"]

    assert match.pattern == "opening_range_breakout"
    assert match.entry == pytest.approx(2.11)


def test_red_to_green_uses_previous_close():
    bars = minute_bars(9, 40, [1.9, 1.92, 1.94, 1.96, 1.98, 1.99, 2.03])

    [match] = [m for m in detect_previous_close_crosses(bars, context_for(bars, previous_close=2.0))
               if m.direction == "long"]

    assert match.pattern == "red_to_green"
    assert match.entry == 2.0
    assert match.stop == pytest.approx(1.91)


def test_vwap_reclaim_after_three_closes_below():
    bars = [
        make_bar(9, 30, 3.0, 3.0, 3.0, 3.0, volume=10_000),
        make_bar(9, 31, 2.0, 2.0, 2.0, 2.0, volume=100),
        make_bar(9, 32, 2.0, 2.0, 2.0, 2.0, volume=100),
        make_bar(9, 33, 2.0, 2.0, 2.0, 2.0, volume=100),
        make_bar(9, 34, 2.0, 3.2, 2.0, 3.1, volume=100),
    ]

    [match] = detect_vwap_crosses(bars, context_for(bars))

    assert (match.pattern, match.direction) == ("vwap_reclaim", "long")
    assert match.entry == 3.2  # last bar's high
    assert match.stop == 2.0


def test_short_patterns_mirror_long():
    closes = [3.0, 2.9, 2.8, 2.7, 2.6, 2.55, 2.6, 2.65, 2.7, 2.65, 2.6, 2.56, 2.53, 2.48]
    bars = minute_bars(9, 30, closes)

    [match] = [m for m in detect_day_extreme_breaks(bars, context_for(bars)) if m.pattern == "low_of_day_break"]

    assert match.direction == "short"
    assert match.entry == pytest.approx(2.54)
    assert match.stop > match.entry


def test_level_break_detectors_return_nothing_without_session():
    context = context_for([])
    for detector in (detect_day_extreme_breaks, detect_premarket_breaks, detect_opening_range_breaks,
                     detect_previous_close_crosses, detect_vwap_crosses):
        assert detector([], context) == []
    no_session = DetectorContext(timeframe="1m", daily_levels=[], session=None, vwap=None)
    bars = minute_bars(9, 30, HOD_CLOSES + [2.44, 2.47, 2.52])
    assert detect_previous_close_crosses(bars, no_session) == []
    assert detect_vwap_crosses(bars, no_session) == []


def test_run_detectors_only_runs_detectors_for_timeframe():
    bars = minute_bars(9, 30, HOD_CLOSES + [2.44, 2.47, 2.52])
    daily_context = DetectorContext(timeframe="daily", daily_levels=[], session=None, vwap=None)

    assert "high_of_day_break" in names(run_detectors(bars, context_for(bars)))
    assert "high_of_day_break" not in names(run_detectors(bars, daily_context))
