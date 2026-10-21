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

    assert verdict.call == "leans_long"  # only the daily trend is known, and it's up
    assert set(verdict.parts) == {"trend"}
    assert "No intraday volume data" in verdict.reasons
    assert "No patterns detected" in verdict.reasons
    assert "No daily support/resistance levels" in verdict.reasons


def test_reasons_are_ordered_by_contribution():
    one_minute, five_minute, daily = rising_inputs()

    verdict = compute_verdict(one_minute, five_minute, daily, session_vwap(one_minute), [], [pattern("long", 0.9)])

    assert verdict.reasons[0].startswith("Above")  # trend carries the largest weight
    assert any("bullish" in reason for reason in verdict.reasons)
