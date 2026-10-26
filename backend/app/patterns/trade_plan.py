"""Turns a detected pattern into an entry/stop/target plan.

The target is 3R unless a daily support/resistance level sits in the way, in
which case the plan shows the reward:risk actually available up to that level.
"""

from dataclasses import dataclass
from datetime import datetime

from app.finviz_client import Bar
from app.patterns.levels import PriceLevel, nearest_level_above, nearest_level_below
from app.patterns.types import Direction, PatternMatch, SetupState

TARGET_R = 3.0
# A stop closer than this to entry is noise, not a plan: it shows as entry = stop =
# target and turns any R maths meaningless.
MIN_RISK_PERCENT = 0.2
EXTENDED_AFTER_R = 1.0
SWING_SIDE_BARS = 2
# Prices are compared after rounding so float noise (2.0 - 1.9 = 0.10000000000000009)
# doesn't push a price that is exactly at a level onto the wrong side.
PRICE_DECIMALS = 6


@dataclass(frozen=True)
class TradePlan:
    direction: Direction
    entry: float
    stop: float
    risk_per_share: float
    risk_percent: float
    target_3r: float
    capped_target: float
    available_reward_risk: float
    blocking_level: float | None
    partial_1r: float
    partial_2r: float
    trailing_stop: float | None


def _price(value: float) -> float:
    return round(value, PRICE_DECIMALS)


def _trailing_stop(bars: list[Bar], direction: Direction) -> float | None:
    for index in range(len(bars) - 1 - SWING_SIDE_BARS, SWING_SIDE_BARS - 1, -1):
        neighbours = bars[index - SWING_SIDE_BARS : index] + bars[index + 1 : index + 1 + SWING_SIDE_BARS]
        bar = bars[index]
        if direction == "long" and all(bar.low < other.low for other in neighbours):
            return bar.low
        if direction == "short" and all(bar.high > other.high for other in neighbours):
            return bar.high
    return None


def _bounded_trailing_stop(bars: list[Bar], direction: Direction, stop: float) -> float | None:
    """A trailing stop only makes sense between the initial stop and the current price."""
    candidate = _trailing_stop(bars, direction)
    if candidate is None or not bars:
        return None
    current = bars[-1].close
    is_between = stop < candidate < current if direction == "long" else current < candidate < stop
    return candidate if is_between else None


def build_trade_plan(match: PatternMatch, daily_levels: list[PriceLevel], recent_bars: list[Bar]) -> TradePlan | None:
    sign = 1 if match.direction == "long" else -1
    risk = _price((match.entry - match.stop) * sign)
    if risk <= 0 or risk / match.entry * 100 < MIN_RISK_PERCENT:
        return None

    target_3r = _price(match.entry + sign * TARGET_R * risk)
    if match.direction == "long":
        nearest = nearest_level_above(daily_levels, match.entry)
        blocking = nearest if nearest is not None and nearest.price < target_3r else None
    else:
        nearest = nearest_level_below(daily_levels, match.entry)
        blocking = nearest if nearest is not None and nearest.price > target_3r else None

    capped_target = _price(blocking.price) if blocking else target_3r
    return TradePlan(
        direction=match.direction,
        entry=match.entry,
        stop=match.stop,
        risk_per_share=risk,
        risk_percent=_price(risk / match.entry * 100),
        target_3r=target_3r,
        capped_target=capped_target,
        available_reward_risk=_price(abs(capped_target - match.entry) / risk),
        blocking_level=capped_target if blocking else None,
        partial_1r=_price(match.entry + sign * risk),
        partial_2r=_price(match.entry + sign * 2 * risk),
        trailing_stop=_bounded_trailing_stop(recent_bars, match.direction, match.stop),
    )


def find_trigger_time(plan: TradePlan, bars: list[Bar]) -> datetime | None:
    """Time of the bar where price last reached the entry: the start of the run of bars,
    ending at the latest one, that touched it (high for a long, low for a short).

    None when the latest bar didn't touch the entry, or when every bar did, since then
    the cross happened before the bars we have.
    """
    sign = 1 if plan.direction == "long" else -1

    def touches_entry(bar: Bar) -> bool:
        favorable_price = bar.high if sign == 1 else bar.low
        return (favorable_price - plan.entry) * sign >= 0

    trigger_time = None
    for bar in reversed(bars):
        if not touches_entry(bar):
            return trigger_time
        trigger_time = bar.time
    return None


def classify_state(plan: TradePlan, last_price: float) -> SetupState:
    sign = 1 if plan.direction == "long" else -1
    progress_r = _price((last_price - plan.entry) * sign / plan.risk_per_share)
    if progress_r <= -1:
        return "invalidated"
    if progress_r < 0:
        return "forming"
    if progress_r < EXTENDED_AFTER_R:
        return "triggered"
    return "extended"
