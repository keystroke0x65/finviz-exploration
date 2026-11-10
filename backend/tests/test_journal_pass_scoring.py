from datetime import date, datetime

import pytest

from app.finviz_client import Bar
from app.journal.pass_scoring import after_pass, score_pass
from app.journal.store import SetupSnapshot
from app.market_time import EASTERN

DAY = date(2026, 11, 9)
SETUP = SetupSnapshot(None, "bull_flag", "1m", "long", entry=2.0, stop=1.9, target=2.3, reward_risk=3.0, score=80.0,
                      state="forming", verdict=None, sliding_scale=None)


def at(hour, minute=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=EASTERN)


def bar(moment, low, high):
    return Bar(moment, low, high, low, high, 1000)


def test_pass_waiting_for_entry_that_reaches_target():
    bars = [bar(at(10, 1), 1.95, 2.05), bar(at(10, 2), 2.05, 2.35)]

    result = score_pass(SETUP, at(10, 0), 1.96, bars)

    assert (result.outcome, result.r) == ("target", pytest.approx(3.0))


def test_pass_already_past_entry_uses_pass_price():
    bars = [bar(at(10, 1), 2.1, 2.3)]

    result = score_pass(SETUP, at(10, 0), 2.1, bars)

    assert result.outcome == "target"
    assert result.r == pytest.approx(1.0)


def test_pass_that_never_reaches_entry_never_filled():
    assert score_pass(SETUP, at(10, 0), 1.95, [bar(at(10, 1), 1.92, 1.98)]).outcome == "never_filled"


def test_stop_before_entry_means_never_filled():
    assert score_pass(SETUP, at(10, 0), 1.95, [bar(at(10, 1), 1.85, 1.97), bar(at(10, 2), 2.0, 2.4)]).outcome == "never_filled"


def test_stop_wins_when_one_bar_touches_both():
    result = score_pass(SETUP, at(10, 0), 2.0, [bar(at(10, 1), 1.85, 2.35)])

    assert (result.outcome, result.r) == ("stop", -1.0)


def test_filled_but_unresolved_by_8pm_is_undecided():
    bars = [bar(at(10, 1), 2.0, 2.1), bar(at(20, 5), 2.5, 2.6)]

    assert score_pass(SETUP, at(10, 0), 2.0, bars).outcome == "undecided"


def test_bars_before_the_pass_are_ignored():
    assert score_pass(SETUP, at(10, 0), 2.0, [bar(at(9, 59), 1.5, 2.5)]).outcome == "undecided"


def test_pass_without_setup_is_not_scored():
    assert score_pass(None, at(10, 0), 2.0, []).outcome == "not_scored"


def test_pass_price_already_past_target_says_so():
    assert score_pass(SETUP, at(10, 0), 2.4, []).outcome == "past_target"


def test_pass_price_already_behind_the_stop_says_so():
    assert score_pass(SETUP, at(10, 0), 1.85, []).outcome == "behind_stop"


def test_short_setup_scores_downward_moves():
    short = SetupSnapshot(None, "bear_flag", "1m", "short", entry=2.0, stop=2.1, target=1.7, reward_risk=3.0, score=80.0,
                          state="forming", verdict=None, sliding_scale=None)

    assert score_pass(short, at(10, 0), 2.05, [bar(at(10, 1), 1.65, 2.0)]).outcome == "target"


def test_after_pass_measures_the_best_and_worst_move_from_the_pass_price():
    bars = [bar(at(9, 59), 1.0, 9.0), bar(at(10, 5), 2.1, 2.45), bar(at(11, 0), 2.05, 2.3), bar(at(20, 0), 1.0, 9.0)]

    result = after_pass(SETUP, "long", at(10, 0), 2.2, bars)

    assert (result.best_price, result.worst_price) == (2.45, 2.05)
    assert result.best_percent == pytest.approx(11.36, abs=0.01)
    assert result.worst_percent == pytest.approx(-6.82, abs=0.01)
    assert (result.best_r, result.worst_r) == (pytest.approx(2.5), pytest.approx(-1.5))


def test_after_pass_without_a_setup_gives_moves_but_no_r():
    result = after_pass(None, "long", at(10, 0), 2.0, [bar(at(10, 5), 1.9, 2.2)])

    assert (result.best_percent, result.best_r) == (pytest.approx(10.0), None)


def test_after_pass_for_a_short_counts_drops_as_the_best_move():
    result = after_pass(None, "short", at(10, 0), 2.0, [bar(at(10, 5), 1.8, 2.1)])

    assert (result.best_price, result.worst_price) == (1.8, 2.1)
    assert (result.best_percent, result.worst_percent) == (pytest.approx(10.0), pytest.approx(-5.0))


def test_after_pass_without_a_price_or_later_bars_is_empty():
    assert after_pass(SETUP, "long", at(10, 0), None, [bar(at(10, 5), 1.9, 2.2)]) is None
    assert after_pass(SETUP, "long", at(10, 0), 2.0, []) is None
