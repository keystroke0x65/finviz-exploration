"""Which of a stock's setups a logged trade or pass was most likely about.

A busy stock can have dozens of setups a day (re-detections, shorts, setups found after the
entry or already stopped out), so the picker offers the ones that fit the trade first.
"""

import math
from datetime import datetime

from app.journal.positions import Direction
from app.setups.store import SetupRecord

# not_tracked only records that the setup was first seen past its entry; it says nothing about
# the setup ending, so such a setup stays live.
BOOKKEEPING_OUTCOMES = {"open", "not_tracked"}


def _copy_key(record: SetupRecord) -> tuple[str, str, str, float]:
    return (record.pattern, record.timeframe, record.direction, record.entry)


def _is_live_at(record: SetupRecord, moment: datetime) -> bool:
    if record.detected_at > moment:
        return False
    if record.outcome in BOOKKEEPING_OUTCOMES or record.resolved_at is None:
        return True
    return record.resolved_at >= moment


def _one_per_setup(records: list[SetupRecord], moment: datetime) -> list[SetupRecord]:
    """The same setup found again after an earlier copy ended shows once: the live copy if any."""
    chosen: dict[tuple[str, str, str, float], SetupRecord] = {}
    for record in sorted(records, key=lambda item: item.detected_at):
        current = chosen.get(_copy_key(record))
        if current is None or _is_live_at(record, moment) or not _is_live_at(current, moment):
            chosen[_copy_key(record)] = record
    return list(chosen.values())


def _fit(record: SetupRecord, moment: datetime, price: float | None) -> tuple[float, float, float]:
    entry_gap = abs(record.entry - price) / price if price else 0.0
    trigger_gap = abs((record.triggered_at - moment).total_seconds()) if record.triggered_at else math.inf
    return (entry_gap, trigger_gap, -record.score)


def match_setups(
    records: list[SetupRecord], moment: datetime, direction: Direction | None, price: float | None
) -> tuple[list[SetupRecord], list[SetupRecord]]:
    """(matches, others): setups live at `moment` in the trade's direction, best fit first,
    then the rest of the day's setups, best score first."""
    matches: list[SetupRecord] = []
    others: list[SetupRecord] = []
    for record in _one_per_setup(records, moment):
        is_match = _is_live_at(record, moment) and (direction is None or record.direction == direction)
        (matches if is_match else others).append(record)
    matches.sort(key=lambda record: _fit(record, moment, price))
    others.sort(key=lambda record: -record.score)
    return matches, others
