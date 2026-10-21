from datetime import datetime, timedelta

import pytest

from app.finviz_client import Bar
from app.market_time import EASTERN
from app.patterns.levels import PriceLevel, find_daily_levels, nearest_level_above, nearest_level_below

BASE_HIGH = 9.0
BASE_LOW = 8.5


def bars_with_highs(highs: list[float]) -> list[Bar]:
    start = datetime(2024, 1, 1, tzinfo=EASTERN)
    return [
        Bar(start + timedelta(days=index), BASE_LOW + 0.2, high, BASE_LOW, BASE_LOW + 0.3, 1000)
        for index, high in enumerate(highs)
    ]


def flat_with_peaks(length: int, peaks: dict[int, float]) -> list[Bar]:
    return bars_with_highs([peaks.get(index, BASE_HIGH) for index in range(length)])


def test_two_matching_swing_highs_make_a_level():
    levels = find_daily_levels(flat_with_peaks(25, {6: 10.0, 17: 10.1}))

    assert levels == [PriceLevel(price=pytest.approx(10.05), touches=2)]


def test_single_swing_is_not_a_level():
    assert find_daily_levels(flat_with_peaks(25, {10: 10.0})) == []


def test_far_apart_swings_stay_separate():
    levels = find_daily_levels(flat_with_peaks(50, {6: 10.0, 17: 10.1, 28: 12.0, 39: 12.1}))

    assert [round(level.price, 2) for level in levels] == [10.05, 12.05]


def test_swing_lows_make_support_levels():
    start = datetime(2024, 1, 1, tzinfo=EASTERN)
    lows = {6: 7.0, 17: 7.05}
    bars = [
        Bar(start + timedelta(days=index), 8.7, BASE_HIGH, lows.get(index, BASE_LOW), 8.8, 1000)
        for index in range(25)
    ]

    assert [round(level.price, 3) for level in find_daily_levels(bars)] == [7.025]


def test_only_last_504_bars_are_used():
    assert find_daily_levels(flat_with_peaks(600, {10: 20.0, 30: 20.1})) == []


def test_no_levels_for_short_history():
    assert find_daily_levels(flat_with_peaks(10, {5: 10.0})) == []


def test_nearest_level_above_and_below_are_strict():
    levels = [PriceLevel(2.0, 2), PriceLevel(2.5, 3), PriceLevel(3.0, 2)]

    assert nearest_level_above(levels, 2.5) == PriceLevel(3.0, 2)
    assert nearest_level_below(levels, 2.5) == PriceLevel(2.0, 2)
    assert nearest_level_above(levels, 3.0) is None
    assert nearest_level_below(levels, 2.0) is None
