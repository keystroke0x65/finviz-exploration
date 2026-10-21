import pytest

from app.patterns.detectors import run_detectors
from app.patterns.detectors.triangles import detect_triangles
from app.patterns.types import DetectorContext
from tests.pattern_shapes import mirrored, shape

CONTEXT = DetectorContext(timeframe="5m", daily_levels=[], session=None, vwap=None)
HIGHS = [2.20, 2.30, 2.50, 2.35, 2.30, 2.38, 2.42, 2.49, 2.40, 2.38, 2.42, 2.45, 2.50, 2.44, 2.43, 2.46, 2.47, 2.48]
LOWS = [2.10, 2.20, 2.40, 2.25, 2.15, 2.25, 2.30, 2.39, 2.30, 2.24, 2.30, 2.35, 2.40, 2.36, 2.33, 2.38, 2.40, 2.42]


def test_ascending_triangle_detected():
    [match] = detect_triangles(shape(HIGHS, LOWS), CONTEXT)

    assert (match.pattern, match.direction) == ("ascending_triangle", "long")
    assert match.entry == 2.50
    assert match.stop == 2.33  # most recent swing low
    assert match.quality_parts["touches"] == pytest.approx(3 / 4)
    assert match.quality_parts["sloping_side"] == 1.0


def test_flat_top_with_flat_lows_is_not_ascending():
    flat_lows = [low if index not in (4, 9, 14) else 2.15 for index, low in enumerate(LOWS)]

    assert detect_triangles(shape(HIGHS, flat_lows), CONTEXT) == []


def test_ascending_triangle_ignored_far_below_top():
    assert detect_triangles(shape(HIGHS, LOWS, last_close=2.20), CONTEXT) == []


def test_descending_triangle_is_short():
    highs, lows = mirrored(HIGHS, LOWS)

    [match] = detect_triangles(shape(highs, lows), CONTEXT)

    assert (match.pattern, match.direction) == ("descending_triangle", "short")
    assert match.entry == pytest.approx(2.50)
    assert match.stop > match.entry


def test_triangles_return_nothing_on_short_or_flat_bars():
    assert detect_triangles(shape(HIGHS[:4], LOWS[:4]), CONTEXT) == []
    assert detect_triangles(shape([2.0] * 30, [1.9] * 30), CONTEXT) == []


def test_triangles_are_registered_on_all_timeframes():
    daily = DetectorContext(timeframe="daily", daily_levels=[], session=None, vwap=None)

    assert "ascending_triangle" in {match.pattern for match in run_detectors(shape(HIGHS, LOWS), daily)}
