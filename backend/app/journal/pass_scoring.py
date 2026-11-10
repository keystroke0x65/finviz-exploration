"""Judges a pass by what the setup would have done from the moment the user passed.

The setup record's own outcome is judged from when the scanner first saw it,
which can't say whether passing *then* was right: a "missed it" pass on a
setup that already hit its target would count as a win the user could never
have had.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.finviz_client import Bar
from app.journal.bars import DAY_END
from app.journal.store import SetupSnapshot
from app.market_time import EASTERN

PassOutcome = Literal["target", "stop", "never_filled", "undecided", "not_scored"]


@dataclass(frozen=True)
class PassScore:
    outcome: PassOutcome
    r: float | None


NOT_SCORED = PassScore("not_scored", None)


def _bars_after(bars: list[Bar], start: datetime) -> list[Bar]:
    day_end = datetime.combine(start.astimezone(EASTERN).date(), DAY_END, tzinfo=EASTERN)
    return sorted((bar for bar in bars if start < bar.time < day_end), key=lambda bar: bar.time)


def _entry_used(setup: SetupSnapshot, pass_price: float | None) -> float | None:
    """The pass price if price was already through the entry, else None (wait for it)."""
    sign = 1 if setup.direction == "long" else -1
    if pass_price is not None and (pass_price - setup.entry) * sign >= 0:
        return pass_price
    return None


def score_pass(setup: SetupSnapshot | None, pass_time: datetime, pass_price: float | None, bars: list[Bar]) -> PassScore:
    if setup is None:
        return NOT_SCORED
    sign = 1 if setup.direction == "long" else -1
    entry = _entry_used(setup, pass_price)
    # Price already at the target or behind the stop: no trade was left to take.
    if entry is not None and ((entry - setup.target) * sign >= 0 or (entry - setup.stop) * sign <= 0):
        return NOT_SCORED
    for bar in _bars_after(bars, pass_time):
        favorable, adverse = (bar.high, bar.low) if sign == 1 else (bar.low, bar.high)
        if entry is None:
            if (adverse - setup.stop) * sign <= 0 and (favorable - setup.entry) * sign < 0:
                return PassScore("never_filled", None)
            if (favorable - setup.entry) * sign < 0:
                continue
            entry = setup.entry
        # A bar touching both can't say which came first: count the stop.
        if (adverse - setup.stop) * sign <= 0:
            return PassScore("stop", -1.0)
        if (favorable - setup.target) * sign >= 0:
            return PassScore("target", abs(setup.target - entry) / abs(entry - setup.stop))
    return PassScore("never_filled" if entry is None else "undecided", None)
