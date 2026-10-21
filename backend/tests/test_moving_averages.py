import pytest

from app.patterns.indicators import ema, sma


def test_ema_seeds_with_simple_average():
    assert ema([1, 2, 3, 4], 3) == [None, None, 2.0, pytest.approx(3.0)]


def test_ema_weights_recent_values():
    # alpha = 2 / (3 + 1) = 0.5: 2.0 + 0.5 * (10 - 2.0) = 6.0
    assert ema([1, 2, 3, 10], 3)[-1] == pytest.approx(6.0)


def test_ema_shorter_than_period_is_all_none():
    assert ema([1, 2], 3) == [None, None]


def test_sma_window():
    assert sma([1, 2, 3, 4, 5], 2) == [None, 1.5, 2.5, 3.5, 4.5]
