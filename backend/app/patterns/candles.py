"""Candlestick signals, used only to confirm (or undercut) a setup at its own levels.

On their own these fire constantly and mean little, so they never create setups:
a bullish signal whose low tags a long setup's stop or entry adds a few points, a
bearish one at its entry takes them away (mirrored for shorts).
"""

from typing import Literal

from app.finviz_client import Bar
from app.patterns.trade_plan import TradePlan

CandleSignal = Literal[
    "bullish_engulfing", "bearish_engulfing", "hammer", "shooting_star", "morning_star", "evening_star", "doji"
]

BULLISH: frozenset[str] = frozenset({"bullish_engulfing", "hammer", "morning_star"})
BEARISH: frozenset[str] = frozenset({"bearish_engulfing", "shooting_star", "evening_star"})

DOJI_MAX_BODY_SHARE = 0.10
WICK_TO_BODY = 2.0
STAR_FIRST_BODY_SHARE = 0.5
STAR_MIDDLE_BODY_SHARE = 0.3
KEY_LEVEL_TOLERANCE = 0.01
CANDLE_POINTS = 5.0
# Prices like 2.05 - 2.045 come out as 0.004999...; compare with a little slack.
EPSILON = 1e-9


def _body(bar: Bar) -> float:
    return abs(bar.close - bar.open)


def _upper_wick(bar: Bar) -> float:
    return bar.high - max(bar.open, bar.close)


def _lower_wick(bar: Bar) -> float:
    return min(bar.open, bar.close) - bar.low


def _is_green(bar: Bar) -> bool:
    return bar.close > bar.open


def _is_red(bar: Bar) -> bool:
    return bar.close < bar.open


def _single_bar_signals(bar: Bar) -> list[CandleSignal]:
    found: list[CandleSignal] = []
    bar_range = bar.high - bar.low
    if bar_range <= 0:
        return found
    body = _body(bar)
    if body <= DOJI_MAX_BODY_SHARE * bar_range + EPSILON:
        found.append("doji")
    if _lower_wick(bar) >= WICK_TO_BODY * body and _upper_wick(bar) <= body + EPSILON and _lower_wick(bar) > 0:
        found.append("hammer")
    if _upper_wick(bar) >= WICK_TO_BODY * body and _lower_wick(bar) <= body + EPSILON and _upper_wick(bar) > 0:
        found.append("shooting_star")
    return found


def _engulfing(previous: Bar, current: Bar) -> list[CandleSignal]:
    if _is_red(previous) and _is_green(current) and current.open <= previous.close and current.close >= previous.open:
        return ["bullish_engulfing"]
    if _is_green(previous) and _is_red(current) and current.open >= previous.close and current.close <= previous.open:
        return ["bearish_engulfing"]
    return []


def _star(first: Bar, middle: Bar, last: Bar) -> list[CandleSignal]:
    first_range = first.high - first.low
    if first_range <= 0 or _body(first) < STAR_FIRST_BODY_SHARE * first_range:
        return []
    if _body(middle) > STAR_MIDDLE_BODY_SHARE * _body(first):
        return []
    midpoint = (first.open + first.close) / 2
    if _is_red(first) and _is_green(last) and last.close > midpoint:
        return ["morning_star"]
    if _is_green(first) and _is_red(last) and last.close < midpoint:
        return ["evening_star"]
    return []


def detect_candle_signals(bars: list[Bar]) -> list[tuple[CandleSignal, Bar]]:
    """Signals completed by the last bar."""
    if not bars:
        return []
    last = bars[-1]
    found = _single_bar_signals(last)
    if len(bars) >= 2:
        found += _engulfing(bars[-2], last)
    if len(bars) >= 3:
        found += _star(bars[-3], bars[-2], last)
    return [(signal, last) for signal in found]


def _near(price: float, level: float) -> bool:
    return abs(price - level) <= level * KEY_LEVEL_TOLERANCE


def _holds_stop(touch: float, stop: float, is_long: bool) -> bool:
    """A test of the stop counts only if the bar stayed on the trade's side of it;
    a wick through the stop already hit it."""
    if is_long:
        return stop <= touch <= stop * (1 + KEY_LEVEL_TOLERANCE)
    return stop * (1 - KEY_LEVEL_TOLERANCE) <= touch <= stop


def candle_points(plan: TradePlan, bars: list[Bar]) -> float:
    """+CANDLE_POINTS when a supporting signal tags the setup's stop or entry,
    -CANDLE_POINTS when an opposing one appears at its entry, 0 otherwise or if both."""
    is_long = plan.direction == "long"
    supporting, opposing = (BULLISH, BEARISH) if is_long else (BEARISH, BULLISH)
    confirms = False
    undercuts = False
    for signal, bar in detect_candle_signals(bars):
        touch = bar.low if is_long else bar.high
        against_touch = bar.high if is_long else bar.low
        if signal in supporting and (_holds_stop(touch, plan.stop, is_long) or _near(touch, plan.entry)):
            confirms = True
        if signal in opposing and _near(against_touch, plan.entry):
            undercuts = True
    if confirms == undercuts:
        return 0.0
    return CANDLE_POINTS if confirms else -CANDLE_POINTS
