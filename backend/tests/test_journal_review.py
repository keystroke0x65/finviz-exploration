from datetime import date, datetime

import pytest

from app.finviz_client import Bar
from app.journal.positions import Fill, compute_trade_figures
from app.journal.review import after_exit, plan_flags
from app.market_time import EASTERN

DAY = date(2026, 11, 9)


def at(hour, minute=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=EASTERN)


def bar(moment, low, high):
    return Bar(moment, low, high, low, high, 1000)


FILLS = [Fill("buy", at(10, 0), 2.0, 100), Fill("sell", at(10, 30), 2.2, 100)]
FIGURES = compute_trade_figures("long", FILLS, 1.9, 2.3, 0.0, at(12))


def test_after_exit_measures_moves_from_the_exit():
    bars = [bar(at(10, 20), 1.5, 3.0), bar(at(11, 0), 2.1, 2.34), bar(at(15, 0), 2.0, 2.3), bar(at(20, 0), 1.0, 5.0)]

    result = after_exit("long", FIGURES, 1.9, bars)

    assert result.best_price == 2.34
    assert result.worst_price == 2.0
    assert result.best_r == pytest.approx(1.4)
    assert result.worst_r == pytest.approx(-2.0)


def test_after_exit_without_stop_gives_prices_only():
    result = after_exit("long", FIGURES, None, [bar(at(11, 0), 2.1, 2.34)])

    assert (result.best_price, result.best_r) == (2.34, None)


def test_after_exit_is_none_while_open():
    open_figures = compute_trade_figures("long", FILLS[:1], 1.9, 2.3, 0.0, at(12))

    assert after_exit("long", open_figures, 1.9, []) is None


def test_after_exit_for_a_short_measures_further_drops_as_positive():
    fills = [Fill("sell", at(10, 0), 2.0, 100), Fill("buy", at(10, 30), 1.8, 100)]
    figures = compute_trade_figures("short", fills, 2.1, 1.7, 0.0, at(12))

    result = after_exit("short", figures, 2.1, [bar(at(11, 0), 1.6, 1.9)])

    assert (result.best_r, result.worst_r) == (pytest.approx(2.0), pytest.approx(-1.0))


def test_held_past_stop_when_price_traded_below_stop_while_holding():
    bars = [bar(at(10, 10), 1.85, 2.1)]

    assert "held_past_stop" in plan_flags("long", FIGURES, 1.9, 2.3, FILLS, bars)


def test_exited_before_target():
    assert plan_flags("long", FIGURES, 1.9, 2.3, FILLS, [bar(at(10, 10), 1.95, 2.1)]) == ["exited_before_target"]


def test_followed_plan_when_target_reached():
    fills = [Fill("buy", at(10, 0), 2.0, 100), Fill("sell", at(10, 30), 2.3, 100)]
    figures = compute_trade_figures("long", fills, 1.9, 2.3, 0.0, at(12))

    assert plan_flags("long", figures, 1.9, 2.3, fills, [bar(at(10, 10), 1.95, 2.2)]) == ["followed_plan"]


def test_no_flags_for_open_trade_within_stop():
    open_figures = compute_trade_figures("long", FILLS[:1], 1.9, 2.3, 0.0, at(12))

    assert plan_flags("long", open_figures, 1.9, 2.3, FILLS[:1], [bar(at(10, 10), 1.95, 2.1)]) == []


def test_a_trade_without_a_plan_gets_no_plan_flags():
    figures = compute_trade_figures("long", FILLS, None, None, 0.0, at(12))

    assert plan_flags("long", figures, None, None, FILLS, []) == []


def test_stopping_out_at_the_plan_stop_follows_the_plan():
    fills = [Fill("buy", at(10, 0), 2.0, 100), Fill("sell", at(10, 30), 1.9, 100)]
    figures = compute_trade_figures("long", fills, 1.9, 2.3, 0.0, at(12))

    assert plan_flags("long", figures, 1.9, 2.3, fills, [bar(at(10, 10), 1.95, 2.05)]) == ["followed_plan"]
