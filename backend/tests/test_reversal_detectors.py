import math

import pytest

from app.patterns.detectors import run_detectors
from app.patterns.detectors.reversals import detect_head_and_shoulders, detect_rounding, detect_triples
from app.patterns.types import DetectorContext
from tests.pattern_shapes import shape, zigzag

FIVE_MINUTE = DetectorContext(timeframe="5m", daily_levels=[], session=None, vwap=None)
ONE_MINUTE = DetectorContext(timeframe="1m", daily_levels=[], session=None, vwap=None)
HEAD_AND_SHOULDERS = [2.00, 2.40, 2.20, 2.60, 2.22, 2.41, 2.23]
TRIPLE_BOTTOM = [2.40, 2.00, 2.30, 2.01, 2.32, 2.005, 2.25]


def flipped(prices, pivot=5.0):
    return [pivot - price for price in prices]


def rounding_closes(depth=0.20, count=30):
    return [2.50 - depth * math.sin(math.pi * index / 34) for index in range(count)]


def from_closes(closes, spread=0.005):
    return shape([close + spread for close in closes], [close - spread for close in closes])


def test_head_and_shoulders_is_short_at_the_neckline():
    [match] = detect_head_and_shoulders(zigzag(HEAD_AND_SHOULDERS), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("head_and_shoulders", "short")
    assert match.entry == pytest.approx(2.21, abs=0.01)  # neckline
    assert match.stop == pytest.approx(2.42, abs=0.01)  # right shoulder


def test_head_must_be_the_highest_peak():
    no_head = [2.00, 2.40, 2.20, 2.35, 2.22, 2.41, 2.23]

    assert detect_head_and_shoulders(zigzag(no_head), FIVE_MINUTE) == []


def test_inverse_head_and_shoulders_is_long():
    [match] = detect_head_and_shoulders(zigzag(flipped(HEAD_AND_SHOULDERS)), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("inverse_head_and_shoulders", "long")
    assert match.stop < match.entry


def test_triple_bottom():
    [match] = detect_triples(zigzag(TRIPLE_BOTTOM), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("triple_bottom", "long")
    assert match.entry == pytest.approx(2.33, abs=0.01)  # the higher neckline
    assert match.stop == pytest.approx(1.99, abs=0.01)


def test_triple_top_is_short():
    [match] = detect_triples(zigzag(flipped(TRIPLE_BOTTOM)), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("triple_top", "short")


def test_rounding_bottom():
    [match] = detect_rounding(from_closes(rounding_closes()), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("rounding_bottom", "long")
    assert match.entry == pytest.approx(2.505, abs=0.005)  # left rim
    assert match.stop == pytest.approx(2.295, abs=0.01)  # bottom


def test_rounding_bottom_needs_depth():
    assert detect_rounding(from_closes(rounding_closes(depth=0.03)), FIVE_MINUTE) == []


def test_rounding_top_is_short():
    [match] = detect_rounding(from_closes(flipped(rounding_closes())), FIVE_MINUTE)

    assert (match.pattern, match.direction) == ("rounding_top", "short")


def test_reversals_only_run_on_5m_and_daily():
    assert "head_and_shoulders" in {m.pattern for m in run_detectors(zigzag(HEAD_AND_SHOULDERS), FIVE_MINUTE)}
    assert "head_and_shoulders" not in {m.pattern for m in run_detectors(zigzag(HEAD_AND_SHOULDERS), ONE_MINUTE)}


def test_reversals_return_nothing_on_short_or_flat_bars():
    flat = shape([2.0] * 40, [1.9] * 40)
    for detector in (detect_head_and_shoulders, detect_triples, detect_rounding):
        assert detector(flat, FIVE_MINUTE) == []
        assert detector(flat[:4], FIVE_MINUTE) == []
