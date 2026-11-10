"""How a closed trade compares with its plan and with what price did after the exit."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.finviz_client import Bar
from app.journal.bars import DAY_END
from app.journal.positions import Direction, Fill, TradeFigures
from app.market_time import EASTERN

PlanFlag = Literal["exited_before_target", "held_past_stop", "followed_plan"]


@dataclass(frozen=True)
class AfterExit:
    """Best and worst price after the last fill, until 8 PM ET that day.

    R is measured from the average exit, in units of the planned risk per share.
    """

    best_r: float | None
    worst_r: float | None
    best_price: float | None
    worst_price: float | None


def after_exit(direction: Direction, figures: TradeFigures, plan_stop: float | None, bars: list[Bar]) -> AfterExit | None:
    if figures.status == "open" or figures.average_exit is None:
        return None
    exit_time = figures.last_fill_at
    day_end = datetime.combine(exit_time.astimezone(EASTERN).date(), DAY_END, tzinfo=EASTERN)
    later = [bar for bar in bars if exit_time < bar.time < day_end]
    if not later:
        return AfterExit(None, None, None, None)
    sign = 1 if direction == "long" else -1
    best = max(bar.high for bar in later) if sign == 1 else min(bar.low for bar in later)
    worst = min(bar.low for bar in later) if sign == 1 else max(bar.high for bar in later)
    risk = None if plan_stop is None else abs(figures.first_price - plan_stop)
    if not risk:
        return AfterExit(None, None, best, worst)
    return AfterExit(
        best_r=(best - figures.average_exit) * sign / risk,
        worst_r=(worst - figures.average_exit) * sign / risk,
        best_price=best,
        worst_price=worst,
    )


def _held_past_stop(direction: Direction, figures: TradeFigures, plan_stop: float, bars: list[Bar]) -> bool:
    # The entry and exit bars are left out: within them, the low may have come
    # before the fill or after the exit.
    holding = [bar for bar in bars if figures.opened_at < bar.time < figures.last_fill_at]
    if figures.status == "open":
        holding = [bar for bar in bars if bar.time > figures.opened_at]
    if direction == "long":
        return any(bar.low < plan_stop for bar in holding)
    return any(bar.high > plan_stop for bar in holding)


def plan_flags(
    direction: Direction,
    figures: TradeFigures,
    plan_stop: float | None,
    plan_target: float | None,
    fills: list[Fill],
    bars: list[Bar],
) -> list[PlanFlag]:
    flags: list[PlanFlag] = []
    if plan_stop is not None and fills and _held_past_stop(direction, figures, plan_stop, bars):
        flags.append("held_past_stop")
    if figures.status == "open":
        return flags
    sign = 1 if direction == "long" else -1
    if plan_target is not None and figures.average_exit is not None and (figures.average_exit - plan_target) * sign < 0:
        flags.append("exited_before_target")
    return flags or ["followed_plan"]
