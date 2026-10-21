import pytest

from app.patterns.detectors import run_detectors
from app.patterns.detectors.converging import detect_pennants, detect_symmetrical_triangles, detect_wedges
from app.patterns.types import DetectorContext
from tests.pattern_shapes import shape, zigzag

ONE_MINUTE = DetectorContext(timeframe="1m", daily_levels=[], session=None, vwap=None)
FIVE_MINUTE = DetectorContext(timeframe="5m", daily_levels=[], session=None, vwap=None)


def flipped(pivots, pivot=5.0):
    return [pivot - price for price in pivots]


PENNANT = [2.00, 2.60, 2.45, 2.56, 2.48, 2.54, 2.50, 2.525]
SYMMETRICAL = [2.00, 2.50, 2.10, 2.42, 2.18, 2.36, 2.24, 2.33]
FALLING_WEDGE = [2.30, 2.60, 2.20, 2.50, 2.15, 2.40, 2.12, 2.33]


def names(matches):
    return {match.pattern for match in matches}


def test_bull_pennant_after_pole():
    [match] = detect_pennants(zigzag(PENNANT), ONE_MINUTE)

    assert (match.pattern, match.direction) == ("bull_pennant", "long")
    assert match.entry == pytest.approx(2.55, abs=0.02)  # latest lower high
    assert match.stop == pytest.approx(2.49, abs=0.02)  # latest higher low
    assert match.stop < match.entry


def test_pennant_needs_a_pole():
    no_pole = [2.55, 2.60, 2.45, 2.56, 2.48, 2.54, 2.50, 2.525]

    assert detect_pennants(zigzag(no_pole), ONE_MINUTE) == []


def test_bear_pennant_is_short():
    [match] = detect_pennants(zigzag(flipped(PENNANT)), ONE_MINUTE)

    assert (match.pattern, match.direction) == ("bear_pennant", "short")
    assert match.stop > match.entry


def test_symmetrical_triangle_breaks_toward_the_nearer_edge():
    [match] = detect_symmetrical_triangles(zigzag(SYMMETRICAL), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("symmetrical_triangle_up", "long")
    assert match.entry == pytest.approx(2.37, abs=0.02)
    assert match.stop == pytest.approx(2.23, abs=0.02)


def test_symmetrical_triangle_down_near_the_lower_edge():
    pivots = SYMMETRICAL[:-1] + [2.27]

    [match] = detect_symmetrical_triangles(zigzag(pivots), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("symmetrical_triangle_down", "short")


def test_widening_shape_is_not_a_symmetrical_triangle():
    widening = [2.00, 2.30, 2.20, 2.40, 2.10, 2.50, 2.00, 2.45]

    assert detect_symmetrical_triangles(zigzag(widening), FIVE_MINUTE) == []


def test_falling_wedge_is_long():
    [match] = detect_wedges(zigzag(FALLING_WEDGE), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("falling_wedge", "long")
    assert match.entry == pytest.approx(2.41, abs=0.02)
    assert match.stop == pytest.approx(2.11, abs=0.02)


def test_parallel_down_channel_is_not_a_wedge():
    channel = [2.30, 2.60, 2.20, 2.50, 2.10, 2.40, 2.00, 2.30]

    assert detect_wedges(zigzag(channel), FIVE_MINUTE) == []


def test_rising_wedge_is_short():
    [match] = detect_wedges(zigzag(flipped(FALLING_WEDGE)), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("rising_wedge", "short")


def test_converging_detectors_return_nothing_on_short_or_flat_bars():
    flat = shape([2.0] * 40, [1.9] * 40)
    for detector in (detect_pennants, detect_symmetrical_triangles, detect_wedges):
        assert detector(flat, FIVE_MINUTE) == []
        assert detector(flat[:4], FIVE_MINUTE) == []


def test_converging_detectors_are_registered():
    assert "falling_wedge" in names(run_detectors(zigzag(FALLING_WEDGE), FIVE_MINUTE))
