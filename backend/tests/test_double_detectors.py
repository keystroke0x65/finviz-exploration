import pytest

from app.patterns.detectors.doubles import detect_doubles
from app.patterns.types import DetectorContext
from tests.pattern_shapes import mirrored, shape

CONTEXT = DetectorContext(timeframe="5m", daily_levels=[], session=None, vwap=None)
W_HIGHS = [2.30, 2.25, 2.20, 2.12, 2.10, 2.15, 2.20, 2.28, 2.32, 2.30, 2.25, 2.18, 2.12, 2.10, 2.15, 2.20, 2.25, 2.29,
           2.30, 2.31]
W_LOWS = [2.20, 2.15, 2.10, 2.03, 2.00, 2.05, 2.10, 2.18, 2.22, 2.20, 2.15, 2.08, 2.03, 2.01, 2.05, 2.10, 2.15, 2.19,
          2.20, 2.21]
VOLUMES = [1000] * 4 + [5000] + [1000] * 8 + [2000] + [1000] * 6


def squeezed(prices, factor=0.1, centre=2.0):
    return [centre + (price - centre) * factor for price in prices]


def test_double_bottom_detected_with_neckline_entry():
    [match] = detect_doubles(shape(W_HIGHS, W_LOWS, VOLUMES), CONTEXT)

    assert (match.pattern, match.direction) == ("double_bottom", "long")
    assert match.entry == 2.32  # the swing high between the lows
    assert match.stop == 2.00  # the lower of the two lows
    assert match.quality_parts["volume_on_retest"] == 1.0


def test_double_bottom_rejects_lows_too_far_apart_in_price():
    lows = [1.90 if index == 13 else low for index, low in enumerate(W_LOWS)]

    assert detect_doubles(shape(W_HIGHS, lows), CONTEXT) == []


def test_double_bottom_needs_real_depth():
    # Same W squeezed to a ~1.5% neckline: below the 2.5% a 5m double needs.
    assert detect_doubles(shape(squeezed(W_HIGHS), squeezed(W_LOWS)), CONTEXT) == []


def test_double_top_is_short():
    highs, lows = mirrored(W_HIGHS, W_LOWS)

    [match] = detect_doubles(shape(highs, lows), CONTEXT)

    assert (match.pattern, match.direction) == ("double_top", "short")
    assert match.entry == pytest.approx(2.68)
    assert match.stop == pytest.approx(3.00)


def test_doubles_return_nothing_on_short_or_flat_bars():
    assert detect_doubles(shape(W_HIGHS[:5], W_LOWS[:5]), CONTEXT) == []
    assert detect_doubles(shape([2.0] * 40, [1.9] * 40), CONTEXT) == []


def test_double_bottom_long_past_its_breakout_is_not_current():
    # Price climbed well above the neckline many bars ago.
    highs = W_HIGHS + [2.40, 2.45, 2.50, 2.55, 2.60, 2.62]
    lows = W_LOWS + [2.30, 2.35, 2.40, 2.45, 2.50, 2.52]

    assert detect_doubles(shape(highs, lows), CONTEXT) == []


def test_range_at_the_top_of_a_run_is_not_a_double_bottom():
    run_highs = [1.00 + 0.05 * index + 0.02 for index in range(20)]
    run_lows = [1.00 + 0.05 * index - 0.02 for index in range(20)]
    range_highs = [2.00, 1.95, 1.93, 1.95, 1.99, 1.96, 1.93, 1.92, 1.94, 1.97]
    range_lows = [1.95, 1.90, 1.88, 1.90, 1.94, 1.91, 1.89, 1.88, 1.89, 1.92]

    patterns = {match.pattern for match in detect_doubles(shape(run_highs + range_highs, run_lows + range_lows), CONTEXT)}

    assert "double_bottom" not in patterns
