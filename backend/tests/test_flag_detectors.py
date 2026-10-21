import pytest

from app.patterns.detectors.flags import detect_flags
from app.patterns.types import DetectorContext
from tests.bar_fixtures import minute_bars

POLE_UP = [2.00, 2.03, 2.06, 2.09, 2.12]
TIGHT_FLAG = [2.11, 2.10, 2.10, 2.11, 2.10]


def context(timeframe="1m"):
    return DetectorContext(timeframe=timeframe, daily_levels=[], session=None, vwap=None)


def pole_then_flag(pole, flag, pole_volume=5000, flag_volume=1000):
    pole_bars = minute_bars(9, 30, pole, volume=pole_volume)
    flag_bars = minute_bars(9, 30 + len(pole), flag, volume=flag_volume)
    return pole_bars + flag_bars


def test_bull_flag_detected_after_pole_and_tight_consolidation():
    [match] = detect_flags(pole_then_flag(POLE_UP, TIGHT_FLAG), context())

    assert (match.pattern, match.direction) == ("bull_flag", "long")
    assert match.entry == pytest.approx(2.12)  # flag's highest high
    assert match.stop == pytest.approx(2.09)  # flag's lowest low
    assert match.quality_parts["volume_contraction"] == 1.0
    assert 0 < match.quality <= 1


def test_flag_without_volume_drop_scores_lower():
    contracting = detect_flags(pole_then_flag(POLE_UP, TIGHT_FLAG), context())[0]
    flat_volume = detect_flags(pole_then_flag(POLE_UP, TIGHT_FLAG, flag_volume=5000), context())[0]

    assert flat_volume.quality_parts["volume_contraction"] == 0.0
    assert flat_volume.quality < contracting.quality


def test_flag_rejected_when_retrace_too_deep():
    assert detect_flags(pole_then_flag(POLE_UP, [2.08, 2.05, 2.03, 2.02, 2.03]), context()) == []


def test_flag_rejected_when_pole_too_small():
    small_pole = [2.00, 2.005, 2.01, 2.015, 2.02]
    assert detect_flags(pole_then_flag(small_pole, [2.015, 2.015, 2.016]), context()) == []


def test_flag_thresholds_differ_by_timeframe():
    bars = pole_then_flag(POLE_UP, TIGHT_FLAG)

    assert detect_flags(bars, context("1m")) != []
    assert detect_flags(bars, context("daily")) == []  # daily needs a 15% pole


def test_bear_flag_mirrors_bull_flag():
    [match] = detect_flags(pole_then_flag([2.12, 2.09, 2.06, 2.03, 2.00], [2.01, 2.02, 2.02, 2.01, 2.02]), context())

    assert (match.pattern, match.direction) == ("bear_flag", "short")
    assert match.entry == pytest.approx(2.00)  # flag's lowest low
    assert match.stop > match.entry


def test_too_few_bars_returns_nothing():
    assert detect_flags(minute_bars(9, 30, [2.0, 2.1]), context()) == []
