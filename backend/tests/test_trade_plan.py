from datetime import datetime

import pytest

from app.market_time import EASTERN
from app.patterns.levels import PriceLevel
from app.patterns.trade_plan import build_trade_plan, classify_state
from app.patterns.types import PatternMatch
from tests.bar_fixtures import make_bar

DETECTED = datetime(2026, 10, 20, 10, 0, tzinfo=EASTERN)


def match(entry=2.00, stop=1.90, direction="long"):
    return PatternMatch(pattern="bull_flag" if direction == "long" else "bear_flag", direction=direction,
                        timeframe="1m", entry=entry, stop=stop, detected_at=DETECTED, quality=0.8,
                        quality_parts={}, key_points=[])


def test_long_plan_uses_three_r_target_when_path_is_clear():
    plan = build_trade_plan(match(), [PriceLevel(2.50, 2)], [])

    assert plan.risk_per_share == pytest.approx(0.10)
    assert plan.target_3r == pytest.approx(2.30)
    assert plan.capped_target == pytest.approx(2.30)
    assert plan.available_reward_risk == pytest.approx(3.0)
    assert plan.blocking_level is None
    assert plan.risk_percent == pytest.approx(5.0)


def test_long_plan_capped_by_daily_resistance():
    plan = build_trade_plan(match(), [PriceLevel(2.15, 3), PriceLevel(2.25, 2)], [])

    assert plan.capped_target == pytest.approx(2.15)
    assert plan.available_reward_risk == pytest.approx(1.5)
    assert plan.blocking_level == pytest.approx(2.15)


def test_level_exactly_at_entry_does_not_cap():
    plan = build_trade_plan(match(), [PriceLevel(2.00, 2)], [])

    assert plan.available_reward_risk == pytest.approx(3.0)


def test_short_plan_capped_by_support_below():
    plan = build_trade_plan(match(entry=2.00, stop=2.10, direction="short"), [PriceLevel(1.85, 2)], [])

    assert plan.target_3r == pytest.approx(1.70)
    assert plan.capped_target == pytest.approx(1.85)
    assert plan.available_reward_risk == pytest.approx(1.5)


def test_partial_levels_at_one_and_two_r():
    plan = build_trade_plan(match(), [], [])

    assert (plan.partial_1r, plan.partial_2r) == (pytest.approx(2.10), pytest.approx(2.20))


def test_trailing_stop_is_most_recent_swing_low():
    lows = [1.95, 1.93, 1.91, 1.94, 1.96, 1.97, 1.95, 1.98, 2.00]
    bars = [make_bar(9, 30 + index, low + 0.02, low + 0.05, low, low + 0.03) for index, low in enumerate(lows)]

    plan = build_trade_plan(match(), [], bars)

    assert plan.trailing_stop == pytest.approx(1.95)  # index 6: lower than 2 bars on each side


def test_trailing_stop_none_without_swing():
    bars = [make_bar(9, 30 + index, 2.0, 2.1, 1.9 + index * 0.01, 2.05) for index in range(6)]

    assert build_trade_plan(match(), [], bars).trailing_stop is None


def test_build_trade_plan_rejects_non_positive_risk():
    assert build_trade_plan(match(entry=2.0, stop=2.0), [], []) is None
    assert build_trade_plan(match(entry=2.0, stop=2.1), [], []) is None
    assert build_trade_plan(match(entry=2.0, stop=1.9, direction="short"), [], []) is None


def test_classify_state_long_boundaries():
    plan = build_trade_plan(match(), [], [])

    assert classify_state(plan, 1.90) == "invalidated"
    assert classify_state(plan, 1.99) == "forming"
    assert classify_state(plan, 2.00) == "triggered"
    assert classify_state(plan, 2.10) == "extended"


def test_classify_state_short_mirrors():
    plan = build_trade_plan(match(entry=2.00, stop=2.10, direction="short"), [], [])

    assert classify_state(plan, 2.10) == "invalidated"
    assert classify_state(plan, 2.01) == "forming"
    assert classify_state(plan, 2.00) == "triggered"
    assert classify_state(plan, 1.90) == "extended"


def test_trailing_stop_dropped_when_above_current_price():
    # Swing low at 2.05 (index 2), but price has since fallen to 2.01.
    lows = [2.10, 2.08, 2.05, 2.07, 2.09, 2.00]
    bars = [make_bar(9, 30 + index, low + 0.02, low + 0.05, low, low + 0.01) for index, low in enumerate(lows)]

    assert build_trade_plan(match(), [], bars).trailing_stop is None


def test_trailing_stop_dropped_when_below_initial_stop():
    lows = [1.95, 1.90, 1.85, 1.92, 1.96, 2.00]
    bars = [make_bar(9, 30 + index, low + 0.02, low + 0.05, low, low + 0.03) for index, low in enumerate(lows)]

    assert build_trade_plan(match(), [], bars).trailing_stop is None


def test_build_trade_plan_rejects_a_stop_too_close_to_trade():
    # 2.3400 entry with a 2.3395 stop: 0.02% risk shows as entry = stop = target.
    assert build_trade_plan(match(entry=2.34, stop=2.3395), [], []) is None
    assert build_trade_plan(match(entry=2.34, stop=2.33), [], []) is not None  # 0.43%
