"""Decides how a recorded setup played out, from the bars that came after it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import TYPE_CHECKING, Literal

from app.finviz_client import Bar
from app.market_time import EASTERN

if TYPE_CHECKING:
    from app.setups.store import SetupRecord

# not_tracked: first seen already past entry, so not a trade anyone could have taken.
Outcome = Literal["open", "target", "stop", "expired", "unresolved", "not_tracked"]

INTRADAY_DEADLINE = time(20, 0)
DAILY_DEADLINE_BARS = 20


@dataclass(frozen=True)
class Resolution:
    outcome: Outcome
    resolved_at: datetime | None
    max_favorable_r: float | None
    max_adverse_r: float | None


def _deadline(record: SetupRecord) -> datetime:
    detected_day = record.detected_at.astimezone(EASTERN).date()
    return datetime.combine(detected_day, INTRADAY_DEADLINE, tzinfo=EASTERN)


def resolve_outcome(record: SetupRecord, bars: list[Bar], now: datetime) -> Resolution:
    if record.first_state != "forming":
        return Resolution("not_tracked", record.detected_at, None, None)
    if not bars or bars[0].time > record.detected_at:
        # Finviz only keeps ~2 weeks of 1m bars; once the detection bar is gone
        # the outcome can't be known, and guessing would corrupt the stats.
        return Resolution("unresolved", None, None, None)

    is_daily = record.timeframe == "daily"
    later_bars = [bar for bar in bars if bar.time > record.detected_at]
    if is_daily:
        later_bars = later_bars[:DAILY_DEADLINE_BARS]
    else:
        later_bars = [bar for bar in later_bars if bar.time < _deadline(record)]

    sign = 1 if record.direction == "long" else -1
    risk = abs(record.entry - record.stop)
    is_filled = False
    max_favorable: float | None = None
    max_adverse: float | None = None

    for bar in later_bars:
        favorable_price, adverse_price = (bar.high, bar.low) if sign == 1 else (bar.low, bar.high)
        if not is_filled:
            # Through the stop before ever reaching entry: the setup failed
            # without a trade, so it must not count as a fill later.
            if (adverse_price - record.stop) * sign <= 0 and (favorable_price - record.entry) * sign < 0:
                return Resolution("expired", bar.time, None, None)
            is_filled = (favorable_price - record.entry) * sign >= 0
            if not is_filled:
                continue
        favorable_r = (favorable_price - record.entry) * sign / risk
        adverse_r = (adverse_price - record.entry) * sign / risk
        max_favorable = favorable_r if max_favorable is None else max(max_favorable, favorable_r)
        max_adverse = adverse_r if max_adverse is None else min(max_adverse, adverse_r)
        # Bars can't say which came first inside one bar, so a bar that touches
        # both counts as the stop: the conservative reading.
        if (adverse_price - record.stop) * sign <= 0:
            return Resolution("stop", bar.time, max_favorable, max_adverse)
        if (favorable_price - record.capped_target) * sign >= 0:
            return Resolution("target", bar.time, max_favorable, max_adverse)

    deadline_passed = (
        len([bar for bar in bars if bar.time > record.detected_at]) >= DAILY_DEADLINE_BARS
        if is_daily
        else now >= _deadline(record)
    )
    if deadline_passed:
        resolved_at = later_bars[-1].time if later_bars else now
        return Resolution("expired", resolved_at, max_favorable, max_adverse)
    return Resolution("open", None, max_favorable, max_adverse)
