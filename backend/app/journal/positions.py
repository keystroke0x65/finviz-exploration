"""Position maths for a logged trade: averages, P&L and R from its fills.

P&L uses the average-cost method: each closing fill realises
(exit price - average entry) x shares, so scaling in and out needs no lot matching.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.market_time import EASTERN

Direction = Literal["long", "short"]
Side = Literal["buy", "sell"]

MAX_FILLS = 50


@dataclass(frozen=True)
class Fill:
    side: Side
    time: datetime
    price: float
    shares: int


@dataclass(frozen=True)
class ClosedPnl:
    """P&L realised by one closing fill, before fees."""

    time: datetime
    pnl: float


@dataclass(frozen=True)
class TradeFigures:
    status: Literal["open", "closed"]
    # Price of the first fill; R is measured from it.
    first_price: float
    average_entry: float
    average_exit: float | None
    shares_held: int
    max_shares: int
    # The largest cost of the position held at any moment.
    money_in: float
    # Value of every opening fill (shares bought for a long, sold short for a short).
    total_bought: float
    realised_pnl: float
    closed_pnl: list[ClosedPnl]
    fees: float
    net_pnl: float
    r_multiple: float | None
    planned_reward_risk: float | None
    opened_at: datetime
    last_fill_at: datetime
    duration_seconds: float


def opening_side(direction: Direction) -> Side:
    return "buy" if direction == "long" else "sell"


def _sorted(fills: list[Fill]) -> list[Fill]:
    return sorted(fills, key=lambda fill: fill.time)


def _describe_time(moment: datetime) -> str:
    return moment.astimezone(EASTERN).strftime("%-I:%M %p")


def validate_fills(direction: Direction, fills: list[Fill]) -> str | None:
    """Why these fills can't make one trade, or None when they can."""
    if not fills:
        return "Add at least one fill."
    if len(fills) > MAX_FILLS:
        return f"A trade can have at most {MAX_FILLS} fills."
    ordered = _sorted(fills)
    if ordered[0].side != opening_side(direction):
        return f"The first fill must be a {opening_side(direction)} for a {direction} trade."
    held = 0
    for index, fill in enumerate(ordered):
        if held == 0 and index > 0:
            return "Shares go back to zero before the last fill; log the rest as a new trade."
        if fill.side == opening_side(direction):
            held += fill.shares
            continue
        if fill.shares > held:
            if direction == "long":
                return f"Fill at {_describe_time(fill.time)} would sell more shares than are held."
            return f"Fill at {_describe_time(fill.time)} would buy back more shares than are short."
        held -= fill.shares
    return None


def validate_plan(direction: Direction, fills: list[Fill], plan_stop: float | None, plan_target: float | None) -> str | None:
    """Why the plan can't be measured against these fills: a stop or target on the wrong side
    of the first fill would turn R into a believable but meaningless number."""
    if not fills:
        return None
    first = _sorted(fills)[0].price
    is_long = direction == "long"
    if plan_stop is not None and (plan_stop >= first if is_long else plan_stop <= first):
        side = "below" if is_long else "above"
        return f"The plan stop ({plan_stop:.2f}) must be {side} the first fill ({first:.2f}) for a {direction} trade."
    if plan_target is not None and (plan_target <= first if is_long else plan_target >= first):
        side = "above" if is_long else "below"
        return f"The plan target ({plan_target:.2f}) must be {side} the first fill ({first:.2f}) for a {direction} trade."
    return None


def _reward_risk(first_price: float, plan_stop: float | None, plan_target: float | None) -> float | None:
    if plan_stop is None or plan_target is None or first_price == plan_stop:
        return None
    return abs(plan_target - first_price) / abs(first_price - plan_stop)


def compute_trade_figures(
    direction: Direction,
    fills: list[Fill],
    plan_stop: float | None,
    plan_target: float | None,
    fees: float,
    now: datetime,
) -> TradeFigures:
    """Figures for fills that already passed validate_fills."""
    ordered = _sorted(fills)
    sign = 1 if direction == "long" else -1
    held = 0
    average_cost = 0.0
    money_in = 0.0
    max_shares = 0
    opened_value = opened_shares = 0.0
    closed_value = closed_shares = 0.0
    closed_pnl: list[ClosedPnl] = []
    for fill in ordered:
        if fill.side == opening_side(direction):
            average_cost = (average_cost * held + fill.price * fill.shares) / (held + fill.shares)
            held += fill.shares
            opened_value += fill.price * fill.shares
            opened_shares += fill.shares
            max_shares = max(max_shares, held)
            money_in = max(money_in, held * average_cost)
            continue
        closed_pnl.append(ClosedPnl(fill.time, (fill.price - average_cost) * fill.shares * sign))
        closed_value += fill.price * fill.shares
        closed_shares += fill.shares
        held -= fill.shares

    is_closed = held == 0
    realised = sum(point.pnl for point in closed_pnl)
    # Fees are booked when the trade closes, with its final fill.
    net = realised - fees if is_closed else realised
    first_price = ordered[0].price
    risk = None if plan_stop is None else abs(first_price - plan_stop) * max_shares
    return TradeFigures(
        status="closed" if is_closed else "open",
        first_price=first_price,
        average_entry=opened_value / opened_shares,
        average_exit=closed_value / closed_shares if closed_shares else None,
        shares_held=held,
        max_shares=max_shares,
        money_in=money_in,
        total_bought=opened_value,
        realised_pnl=realised,
        closed_pnl=closed_pnl,
        fees=fees,
        net_pnl=net,
        r_multiple=net / risk if risk else None,
        planned_reward_risk=_reward_risk(first_price, plan_stop, plan_target),
        opened_at=ordered[0].time,
        last_fill_at=ordered[-1].time,
        duration_seconds=((ordered[-1].time if is_closed else now) - ordered[0].time).total_seconds(),
    )
