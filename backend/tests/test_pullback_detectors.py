import pytest

from app.patterns.detectors.pullbacks import detect_first_pullbacks, detect_micro_pullbacks
from app.patterns.types import DetectorContext, SessionLevels
from tests.pattern_shapes import mirrored, shape

PLAIN = DetectorContext(timeframe="1m", daily_levels=[], session=None, vwap=None)


def with_previous_close(previous_close):
    session = SessionLevels(None, None, None, None, None, None, previous_close)
    return DetectorContext(timeframe="1m", daily_levels=[], session=session, vwap=None)


RUN_HIGHS, RUN_LOWS = [2.01, 2.03, 2.06, 2.09], [1.99, 2.01, 2.03, 2.06]

GAP_HIGHS = [2.25, 2.32, 2.40, 2.46, 2.50, 2.45, 2.42]
GAP_LOWS = [2.18, 2.24, 2.31, 2.38, 2.43, 2.38, 2.36]


def test_micro_pullback_after_strong_run():
    bars = shape(RUN_HIGHS + [2.08], RUN_LOWS + [2.06], volumes=[5000] * 4 + [1000])

    [match] = detect_micro_pullbacks(bars, PLAIN)

    assert (match.pattern, match.direction) == ("micro_pullback", "long")
    assert (match.entry, match.stop) == (2.08, 2.06)
    assert match.quality_parts["volume_drop"] == 1.0


def test_micro_pullback_rejects_deep_pullback():
    bars = shape(RUN_HIGHS + [2.08], RUN_LOWS + [2.02])

    assert detect_micro_pullbacks(bars, PLAIN) == []


def test_micro_pullback_needs_a_real_run():
    bars = shape([2.001, 2.003, 2.006, 2.009, 2.008], [1.999, 2.001, 2.003, 2.006, 2.006])

    assert detect_micro_pullbacks(bars, PLAIN) == []


def test_first_pullback_after_gap_up():
    [match] = detect_first_pullbacks(shape(GAP_HIGHS, GAP_LOWS), with_previous_close(2.00))

    assert (match.pattern, match.direction) == ("first_pullback", "long")
    assert match.entry == 2.42  # high of the last pullback bar
    assert match.stop == 2.36  # pullback low


def test_first_pullback_still_current_on_the_breaking_bar():
    bars = shape(GAP_HIGHS + [2.47], GAP_LOWS + [2.40])

    [match] = detect_first_pullbacks(bars, with_previous_close(2.00))

    assert match.entry == 2.42


def test_no_first_pullback_without_gap():
    assert detect_first_pullbacks(shape(GAP_HIGHS, GAP_LOWS), with_previous_close(2.20)) == []


def test_second_pullback_is_not_a_first_pullback():
    highs = [2.25, 2.32, 2.40, 2.35, 2.33, 2.45, 2.50, 2.45, 2.42]
    lows = [2.18, 2.24, 2.31, 2.28, 2.27, 2.36, 2.43, 2.38, 2.36]

    assert detect_first_pullbacks(shape(highs, lows), with_previous_close(2.00)) == []


def test_first_bounce_fail_after_gap_down():
    highs, lows = mirrored(GAP_HIGHS, GAP_LOWS)

    [match] = detect_first_pullbacks(shape(highs, lows), with_previous_close(3.00))

    assert (match.pattern, match.direction) == ("first_bounce_fail", "short")
    assert match.entry == pytest.approx(5 - 2.42)
    assert match.stop == pytest.approx(5 - 2.36)


def test_pullbacks_return_nothing_on_short_or_flat_bars():
    assert detect_micro_pullbacks(shape([2.0, 2.1], [1.9, 2.0]), PLAIN) == []
    assert detect_micro_pullbacks(shape([2.0] * 20, [1.9] * 20), PLAIN) == []
    assert detect_first_pullbacks(shape([2.0] * 20, [1.9] * 20), with_previous_close(1.5)) == []
    assert detect_first_pullbacks(shape(GAP_HIGHS, GAP_LOWS), PLAIN) == []
