import pytest

from app.patterns.detectors import run_detectors
from app.patterns.detectors.abcd import detect_abcd
from app.patterns.types import DetectorContext
from tests.pattern_shapes import mirrored, shape

CONTEXT = DetectorContext(timeframe="1m", daily_levels=[], session=None, vwap=None)
HIGHS = [2.05, 2.10, 2.15, 2.22, 2.30, 2.36, 2.40, 2.35, 2.30, 2.26, 2.24, 2.26, 2.28, 2.31, 2.33, 2.31, 2.29, 2.28,
         2.29, 2.30, 2.31]
LOWS = [2.00, 2.05, 2.10, 2.16, 2.24, 2.30, 2.34, 2.28, 2.24, 2.21, 2.20, 2.21, 2.23, 2.26, 2.28, 2.27, 2.26, 2.25,
        2.26, 2.27, 2.28]


def with_low(index, value):
    return [value if position == index else low for position, low in enumerate(LOWS)]


def test_abcd_detected_with_c_entry_and_d_stop():
    [match] = detect_abcd(shape(HIGHS, LOWS), CONTEXT)

    assert (match.pattern, match.direction) == ("abcd", "long")
    assert match.entry == 2.33  # C
    assert match.stop == 2.25  # D, the higher low after C
    assert match.quality_parts["retrace"] == pytest.approx(1.0)  # B retraced exactly half the spike
    assert [price for _, price in match.key_points] == [2.40, 2.20, 2.33, 2.25]


def test_abcd_rejects_lower_low_at_d():
    assert detect_abcd(shape(HIGHS, with_low(17, 2.15)), CONTEXT) == []


def test_abcd_rejects_retrace_too_deep():
    assert detect_abcd(shape(HIGHS, with_low(10, 2.08)), CONTEXT) == []


def test_inverse_abcd_is_short():
    highs, lows = mirrored(HIGHS, LOWS)

    [match] = detect_abcd(shape(highs, lows), CONTEXT)

    assert (match.pattern, match.direction) == ("inverse_abcd", "short")
    assert match.entry == pytest.approx(5 - 2.33)
    assert match.stop == pytest.approx(5 - 2.25)


def test_abcd_not_run_on_daily():
    daily = DetectorContext(timeframe="daily", daily_levels=[], session=None, vwap=None)

    assert "abcd" not in {match.pattern for match in run_detectors(shape(HIGHS, LOWS), daily)}
    assert "abcd" in {match.pattern for match in run_detectors(shape(HIGHS, LOWS), CONTEXT)}


def test_abcd_returns_nothing_on_short_or_flat_bars():
    assert detect_abcd(shape(HIGHS[:5], LOWS[:5]), CONTEXT) == []
    assert detect_abcd(shape([2.0] * 40, [1.9] * 40), CONTEXT) == []
