from app.patterns.candles import CANDLE_POINTS, candle_points, detect_candle_signals
from app.patterns.trade_plan import TradePlan
from tests.bar_fixtures import make_bar


def signals(*ohlc):
    bars = [make_bar(9, 30 + index, *values) for index, values in enumerate(ohlc)]
    return {signal for signal, _ in detect_candle_signals(bars)}


def test_bullish_engulfing():
    assert "bullish_engulfing" in signals((2.10, 2.12, 2.01, 2.02), (2.00, 2.15, 1.99, 2.13))


def test_bearish_engulfing():
    assert "bearish_engulfing" in signals((2.02, 2.11, 2.01, 2.10), (2.12, 2.13, 1.98, 2.00))


def test_hammer_and_shooting_star():
    assert "hammer" in signals((2.10, 2.11, 2.00, 2.105))  # long lower wick, small body at the top
    assert "shooting_star" in signals((2.00, 2.10, 1.995, 2.005))  # long upper wick


def test_morning_and_evening_star():
    assert "morning_star" in signals((2.20, 2.21, 2.05, 2.06), (2.05, 2.06, 2.02, 2.04), (2.05, 2.18, 2.04, 2.17))
    assert "evening_star" in signals((2.05, 2.21, 2.04, 2.20), (2.21, 2.24, 2.20, 2.22), (2.21, 2.22, 2.08, 2.09))


def test_doji():
    assert "doji" in signals((2.05, 2.10, 2.00, 2.051))


def test_plain_bar_has_no_signal():
    assert signals((2.00, 2.10, 1.99, 2.09)) == set()


def long_plan(entry=2.10, stop=2.00):
    return TradePlan(direction="long", entry=entry, stop=stop, risk_per_share=entry - stop, risk_percent=5.0,
                     target_3r=entry + 3 * (entry - stop), capped_target=entry + 3 * (entry - stop),
                     available_reward_risk=3.0, blocking_level=None, partial_1r=0, partial_2r=0, trailing_stop=None)


def test_hammer_at_the_stop_confirms_a_long_setup():
    bars = [make_bar(9, 30, 2.08, 2.09, 2.001, 2.085)]  # hammer whose low tags the 2.00 stop

    assert candle_points(long_plan(), bars) == CANDLE_POINTS


def test_shooting_star_at_entry_counts_against_a_long_setup():
    bars = [make_bar(9, 30, 2.05, 2.11, 2.045, 2.055)]  # rejected right at the 2.10 entry

    assert candle_points(long_plan(), bars) == -CANDLE_POINTS


def test_candle_away_from_key_levels_is_ignored():
    bars = [make_bar(9, 30, 2.40, 2.41, 2.30, 2.405)]  # a hammer, but nowhere near 2.00 or 2.10

    assert candle_points(long_plan(), bars) == 0.0
