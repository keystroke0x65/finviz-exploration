from datetime import date

import pytest

from app.patterns.indicators import session_levels, session_vwap
from tests.bar_fixtures import TRADING_DAY, daily_bars, make_bar


def test_vwap_weights_by_volume():
    bars = [make_bar(9, 30, 10, 10, 10, 10, volume=100), make_bar(9, 31, 20, 20, 20, 20, volume=300)]

    assert session_vwap(bars) == [10.0, pytest.approx(17.5)]


def test_vwap_resets_each_eastern_day():
    bars = [
        make_bar(19, 59, 10, 10, 10, 10, volume=500),
        make_bar(4, 0, 12, 12, 12, 12, volume=100, day=date(2026, 10, 21)),
    ]

    assert session_vwap(bars) == [10.0, 12.0]


def test_vwap_ignores_bars_before_four_am():
    bars = [make_bar(3, 59, 50, 50, 50, 50, volume=1000), make_bar(4, 0, 10, 10, 10, 10, volume=100)]

    assert session_vwap(bars) == [None, 10.0]


def test_vwap_is_none_until_volume_trades():
    assert session_vwap([make_bar(4, 0, 10, 10, 10, 10, volume=0)]) == [None]


def test_session_levels_split_premarket_and_regular():
    bars = [
        make_bar(4, 0, 2.0, 2.4, 1.9, 2.2),
        make_bar(9, 29, 2.2, 2.3, 2.1, 2.2),
        make_bar(9, 30, 2.2, 2.6, 2.15, 2.5),
        make_bar(15, 59, 2.5, 2.55, 2.0, 2.1),
        make_bar(16, 0, 2.1, 3.0, 1.5, 2.0),  # after-hours: not part of the day range
    ]

    levels = session_levels(bars, [], TRADING_DAY)

    assert (levels.premarket_high, levels.premarket_low) == (2.4, 1.9)
    assert (levels.day_high, levels.day_low) == (2.6, 2.0)


def test_session_levels_opening_range_is_first_five_minutes():
    bars = [make_bar(9, 30 + offset, 2.0, 2.0 + offset * 0.1, 1.9 - offset * 0.01, 2.0) for offset in range(6)]

    levels = session_levels(bars, [], TRADING_DAY)

    assert levels.opening_range_high == pytest.approx(2.4)  # 09:34 bar, not 09:35
    assert levels.opening_range_low == pytest.approx(1.86)


def test_session_levels_previous_close_from_daily_bars():
    history = daily_bars([1.0, 1.5, 1.8], start=date(2026, 10, 16))  # Fri 16, Mon 19, Tue 20

    levels = session_levels([], history, TRADING_DAY)

    assert levels.previous_close == 1.5


def test_session_levels_empty_when_no_bars_today():
    yesterday = [make_bar(9, 30, 2.0, 2.5, 1.9, 2.1, day=date(2026, 10, 19))]
    history = daily_bars([1.0, 1.5], start=date(2026, 10, 16))

    levels = session_levels(yesterday, history, TRADING_DAY)

    assert levels.premarket_high is None
    assert levels.day_high is None
    assert levels.opening_range_high is None
    assert levels.previous_close == 1.5
