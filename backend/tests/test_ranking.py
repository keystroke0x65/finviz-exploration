from datetime import datetime

import pytest

from app.market_time import EASTERN
from app.patterns.ranking import score_setup
from app.patterns.trade_plan import TradePlan
from app.patterns.types import PatternMatch

NOW = datetime(2026, 10, 20, 10, 0, tzinfo=EASTERN)


def match(direction="long", timeframe="1m", quality=0.6):
    return PatternMatch(pattern="bull_flag", direction=direction, timeframe=timeframe, entry=2.0, stop=1.9,
                        detected_at=NOW, quality=quality, quality_parts={}, key_points=[])


def plan(available=3.0):
    return TradePlan(direction="long", entry=2.0, stop=1.9, risk_per_share=0.1, risk_percent=5.0, target_3r=2.3,
                     capped_target=2.0 + available * 0.1, available_reward_risk=available, blocking_level=None,
                     partial_1r=2.1, partial_2r=2.2, trailing_stop=None)


def score(available=3.0, state="forming", others=(), relative_volume=2.0, setup=None):
    return score_setup(setup or match(), plan(available), state, relative_volume, list(others))


def test_reward_risk_dominates_score():
    assert score(available=3.0).total > score(available=1.0).total + 20


def test_no_extra_credit_above_three_r():
    assert score(available=4.5).total == score(available=3.0).total


def test_extended_setups_rank_below_fresh_ones():
    assert score(state="extended").total < score(state="triggered").total == score(state="forming").total


def test_agreement_on_another_timeframe_adds_bonus():
    assert score(others=[match(timeframe="5m")]).total > score().total


def test_same_timeframe_match_is_not_agreement():
    assert score(others=[match(timeframe="1m")]).total == score().total


def test_opposite_pattern_on_higher_timeframe_penalises():
    penalised = score(others=[match(direction="short", timeframe="daily")])

    assert penalised.parts["conflict"] == pytest.approx(-20.0)
    assert penalised.total < score().total


def test_opposite_pattern_on_lower_timeframe_does_not_penalise():
    setup = match(timeframe="5m")

    assert score(setup=setup, others=[match(direction="short", timeframe="1m")]).parts["conflict"] == 0.0


def test_missing_relative_volume_scores_zero_volume():
    assert score(relative_volume=None).parts["volume"] == 0.0


def test_parts_sum_to_total():
    breakdown = score(others=[match(timeframe="5m")])

    assert sum(breakdown.parts.values()) == pytest.approx(breakdown.total, abs=0.1)


def stats(trades, average_r):
    from app.setups.track_record import PatternStats

    return PatternStats(pattern="bull_flag", timeframe="1m", trades=trades, wins=0, losses=0, expired_after_fill=0,
                        win_rate=0.5, average_r=average_r, average_max_favorable_r=1.0, not_trades=0, still_open=0)


def test_track_record_ignored_below_thirty_trades():
    base = score()
    thin = score_setup(match(), plan(), "forming", 2.0, [], track_record=stats(29, 1.0))

    assert thin.parts["track_record"] == 0.0
    assert thin.total == base.total


def test_good_history_raises_and_bad_history_lowers_the_score():
    good = score_setup(match(), plan(), "forming", 2.0, [], track_record=stats(40, 0.5))
    bad = score_setup(match(), plan(available=2.0), "forming", 2.0, [], track_record=stats(40, -3.0))

    assert good.parts["track_record"] == pytest.approx(7.5)
    assert bad.parts["track_record"] == pytest.approx(-15.0)  # capped at -1R
