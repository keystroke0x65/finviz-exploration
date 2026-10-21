import math

import pytest

from app.patterns.detectors import run_detectors
from app.patterns.detectors.ranges_cups import detect_cups, detect_ranges
from app.patterns.types import DetectorContext
from tests.pattern_shapes import shape, zigzag

ONE_MINUTE = DetectorContext(timeframe="1m", daily_levels=[], session=None, vwap=None)
FIVE_MINUTE = DetectorContext(timeframe="5m", daily_levels=[], session=None, vwap=None)
RANGE = [2.00, 2.08, 2.00, 2.08, 2.00, 2.08, 2.00, 2.07]


def from_closes(closes, spread=0.005):
    return shape([close + spread for close in closes], [close - spread for close in closes])


def cup_closes(handle=(2.48, 2.46, 2.45, 2.44, 2.45), low_at=13):
    cup = [2.50 - 0.30 * math.sin(math.pi * min(index, 26) / 26) for index in range(27)]
    if low_at != 13:  # move the bottom off-centre
        cup = [2.50 - 0.30 * math.sin(math.pi / 2 * min(index / low_at, 1)) if index <= low_at
               else 2.20 + 0.30 * (index - low_at) / (26 - low_at) for index in range(27)]
    return cup + list(handle)


def flipped(prices, pivot=5.0):
    return [pivot - price for price in prices]


def test_range_breakout_near_the_top():
    [match] = detect_ranges(zigzag(RANGE), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("range_breakout", "long")
    assert match.entry == pytest.approx(2.09)
    assert match.stop == pytest.approx(1.99)


def test_range_breakdown_near_the_bottom():
    [match] = detect_ranges(zigzag(RANGE[:-1] + [2.01]), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("range_breakdown", "short")


def test_range_too_wide_for_the_timeframe():
    assert detect_ranges(zigzag(RANGE), ONE_MINUTE) == []  # 5% span; 1m ranges must be within 3%


def test_cup_and_handle():
    [match] = detect_cups(from_closes(cup_closes()), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("cup_and_handle", "long")
    assert match.entry == pytest.approx(2.505, abs=0.005)  # right rim
    assert match.stop == pytest.approx(2.435, abs=0.01)  # handle low


def test_cup_needs_its_low_in_the_middle():
    assert detect_cups(from_closes(cup_closes(low_at=3)), FIVE_MINUTE) == []


def test_cup_handle_too_deep():
    assert detect_cups(from_closes(cup_closes(handle=(2.45, 2.38, 2.32, 2.30, 2.33))), FIVE_MINUTE) == []


def test_inverted_cup_and_handle_is_short():
    [match] = detect_cups(from_closes(flipped(cup_closes())), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("inverted_cup_and_handle", "short")
    assert match.stop > match.entry


def test_range_and_cup_detectors_return_nothing_on_short_or_flat_bars():
    flat = shape([2.0] * 40, [1.9] * 40)
    for detector in (detect_ranges, detect_cups):
        assert detector(flat, FIVE_MINUTE) == []
        assert detector(flat[:4], FIVE_MINUTE) == []


def test_range_and_cup_detectors_are_registered():
    assert "cup_and_handle" in {m.pattern for m in run_detectors(from_closes(cup_closes()), FIVE_MINUTE)}


def test_range_not_called_with_price_in_the_middle():
    # 1.99-2.09 range on 5m; 2.055 is within 2% of the top but only 65% of the way up.
    assert detect_ranges(zigzag(RANGE[:-1] + [2.055]), FIVE_MINUTE) == []
