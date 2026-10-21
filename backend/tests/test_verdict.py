from datetime import date, datetime, timedelta

from app.finviz_client import Bar
from app.market_time import EASTERN
from app.patterns.indicators import session_vwap
from app.patterns.levels import PriceLevel
from app.patterns.types import PatternMatch
from app.patterns.verdict import compute_verdict
from tests.bar_fixtures import daily_bars, minute_bars

NOW = datetime(2026, 10, 20, 11, 0, tzinfo=EASTERN)


def trending(start, step, count=60):
    return [round(start + step * index, 4) for index in range(count)]


def pattern(direction, quality=0.8):
    return PatternMatch(pattern="bull_flag" if direction == "long" else "bear_flag", direction=direction,
                        timeframe="5m", entry=2.0, stop=1.9 if direction == "long" else 2.1, detected_at=NOW,
                        quality=quality, quality_parts={}, key_points=[])


def rising_inputs():
    one_minute = minute_bars(9, 30, trending(2.0, 0.01))
    five_minute = minute_bars(9, 30, trending(2.0, 0.05, 30), step_minutes=5)
    daily = daily_bars(trending(1.0, 0.03, 80), start=date(2026, 6, 1))
    return one_minute, five_minute, daily


def test_uptrend_with_bull_patterns_leans_long():
    one_minute, five_minute, daily = rising_inputs()

    verdict = compute_verdict(one_minute, five_minute, daily, session_vwap(one_minute),
                              [PriceLevel(1.0, 2), PriceLevel(9.0, 2)], [pattern("long")])

    assert verdict.call == "leans_long"
    assert verdict.score >= 0.25
    assert verdict.parts["trend"] == 1.0
    assert verdict.parts["patterns"] == 1.0


def test_downtrend_with_bear_patterns_leans_short():
    one_minute = minute_bars(9, 30, trending(3.0, -0.01))
    five_minute = minute_bars(9, 30, trending(3.0, -0.05, 30), step_minutes=5)
    daily = daily_bars(trending(5.0, -0.03, 80), start=date(2026, 6, 1))

    verdict = compute_verdict(one_minute, five_minute, daily, session_vwap(one_minute), [], [pattern("short")])

    assert verdict.call == "leans_short"
    assert verdict.parts["trend"] == -1.0


def test_mixed_signals_give_no_clear_edge():
    # Price drifts up, but volume is heavier on the down bars and the pattern is bearish.
    start = datetime(2026, 10, 20, 9, 30, tzinfo=EASTERN)
    one_minute = []
    price = 2.0
    for index in range(40):
        is_up = index % 2 == 0
        close = price + (0.03 if is_up else -0.02)
        one_minute.append(Bar(start + timedelta(minutes=index), price, max(price, close) + 0.01,
                              min(price, close) - 0.01, close, 1000 if is_up else 3000))
        price = close
    five_minute = minute_bars(9, 30, trending(2.0, 0.02, 30), step_minutes=5)

    verdict = compute_verdict(one_minute, five_minute, [], session_vwap(one_minute), [], [pattern("short")])

    assert verdict.call == "no_clear_edge"
    assert -0.25 < verdict.score < 0.25


def test_verdict_with_missing_inputs_uses_what_is_available():
    daily = daily_bars(trending(1.0, 0.03, 80), start=date(2026, 6, 1))

    verdict = compute_verdict([], [], daily, None, [], [])

    # Only the daily trend is known: too little for a call, but it's still reported.
    assert verdict.call == "no_clear_edge"
    assert verdict.reasons[0] == "Not enough data for a call"
    assert set(verdict.parts) == {"trend"}
    assert verdict.parts["trend"] == 1.0
    assert "No intraday volume data" in verdict.reasons
    assert "No patterns detected" in verdict.reasons
    assert "No daily support/resistance levels" in verdict.reasons


def test_reasons_are_ordered_by_contribution():
    one_minute, five_minute, daily = rising_inputs()

    verdict = compute_verdict(one_minute, five_minute, daily, session_vwap(one_minute), [], [pattern("long", 0.9)])

    assert verdict.reasons[0].startswith("Above")  # trend carries the largest weight
    assert any("bullish" in reason for reason in verdict.reasons)


def test_single_pattern_alone_is_not_enough_for_a_call():
    verdict = compute_verdict([], [], [], None, [], [pattern("long", 0.2)])

    assert verdict.call == "no_clear_edge"
    assert verdict.reasons[0] == "Not enough data for a call"


def test_trend_and_patterns_disagreeing_is_no_clear_edge():
    one_minute, five_minute, daily = rising_inputs()  # trend and volume both up

    verdict = compute_verdict(one_minute, five_minute, daily, session_vwap(one_minute), [], [pattern("short")])

    assert verdict.parts["trend"] == 1.0 and verdict.parts["patterns"] == -1.0
    assert verdict.call == "no_clear_edge"
    assert "Trend and patterns disagree" in verdict.reasons


def test_distant_support_is_not_bearish_for_a_stock_with_no_resistance():
    one_minute, five_minute, daily = rising_inputs()  # last price ~2.59

    verdict = compute_verdict(one_minute, five_minute, daily, session_vwap(one_minute), [PriceLevel(1.5, 2)], [])

    assert verdict.parts["location"] == 0.0  # 20% room overhead (none), support capped at 20%


def test_low_relative_volume_weakens_the_volume_signal():
    one_minute, five_minute, daily = rising_inputs()  # every 1m bar is an up bar

    normal = compute_verdict(one_minute, five_minute, daily, None, [], [], relative_volume=3.0)
    quiet = compute_verdict(one_minute, five_minute, daily, None, [], [], relative_volume=0.75)

    assert normal.parts["volume"] == 1.0
    assert quiet.parts["volume"] == 0.5
    assert any("3.0x relative volume" in reason for reason in normal.reasons)
