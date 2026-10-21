from datetime import datetime, timedelta

from app.finviz_client import Bar
from app.market_time import EASTERN
from app.patterns.swings import Swing, find_swings


def bars(highs, lows):
    start = datetime(2026, 10, 20, 9, 30, tzinfo=EASTERN)
    return [Bar(start + timedelta(minutes=i), low, high, low, high, 100) for i, (high, low) in enumerate(zip(highs, lows))]


def test_find_swings_marks_highs_and_lows():
    highs = [2.0, 2.1, 2.5, 2.2, 2.1, 2.2, 2.3]
    lows = [1.9, 2.0, 2.2, 1.95, 1.8, 1.9, 2.0]

    assert find_swings(bars(highs, lows)) == [Swing(2, 2.5, True), Swing(4, 1.8, False)]


def test_find_swings_ignores_flat_stretches():
    assert find_swings(bars([2.0] * 9, [1.9] * 9)) == []


def test_find_swings_needs_full_window():
    # A peak at the last bar has no bars after it to confirm it.
    assert find_swings(bars([2.0, 2.1, 2.2, 2.3, 2.9], [1.9, 2.0, 2.1, 2.2, 2.8])) == []


def test_plateau_of_equal_highs_is_one_swing():
    highs = [1.00, 1.01, 1.05, 1.05, 1.02, 1.00]
    lows = [0.95, 0.96, 1.00, 1.00, 0.97, 0.95]

    assert [swing for swing in find_swings(bars(highs, lows)) if swing.is_high] == [Swing(2, 1.05, True)]


def test_plateau_of_equal_lows_is_one_swing():
    highs = [1.10, 1.08, 1.03, 1.03, 1.06, 1.10]
    lows = [1.05, 1.02, 0.98, 0.98, 1.01, 1.05]

    assert [swing for swing in find_swings(bars(highs, lows)) if not swing.is_high] == [Swing(2, 0.98, False)]
