from datetime import date, datetime, timedelta

import pytest

from app.errors import FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import Bar
from app.journal.bars import (
    BARS_RETRY_WARNING,
    aggregate_bars,
    complete_pending_days,
    days_needed,
    read_bars,
    save_bar_days,
    save_bars_for_entry,
)
from app.journal.positions import Fill
from app.journal.store import EMPTY_FACTS, NewEntry, create_entry
from app.market_time import EASTERN

MONDAY = date(2026, 11, 9)
TUESDAY = date(2026, 11, 10)


def bar(day: date, hour: int, minute: int, price: float = 2.0) -> Bar:
    return Bar(datetime(day.year, day.month, day.day, hour, minute, tzinfo=EASTERN), price, price + 0.1, price - 0.1,
               price, 1000)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=EASTERN)


class FakeFinviz:
    def __init__(self, bars=None, error=None):
        self.bars = bars or []
        self.error = error
        self.calls = 0

    def __call__(self, ticker, interval):
        self.calls += 1
        assert interval == "1m"
        if self.error:
            raise self.error
        return self.bars


def trade(fills, ticker="HOST"):
    return NewEntry("trade", ticker, "long", fills[0].time, None, EMPTY_FACTS, None, None, 0.0, [], [], "", None, fills)


def test_days_needed_for_a_closed_multi_day_trade():
    entry = trade([Fill("buy", at(MONDAY, 15), 2.0, 100), Fill("sell", at(date(2026, 11, 12), 10), 2.5, 100)])

    assert days_needed(entry, at(date(2026, 11, 20), 10)) == [MONDAY, TUESDAY, date(2026, 11, 11), date(2026, 11, 12)]


def test_days_needed_for_an_open_trade_runs_to_today_and_skips_weekends():
    entry = trade([Fill("buy", at(date(2026, 11, 6), 15), 2.0, 100)])

    assert days_needed(entry, at(MONDAY, 10)) == [date(2026, 11, 6), MONDAY]


def test_save_bar_days_keeps_only_the_days_session(db_conn):
    finviz = FakeFinviz([bar(MONDAY, 3, 59), bar(MONDAY, 4, 0), bar(MONDAY, 19, 59), bar(TUESDAY, 9, 30)])

    save_bar_days(db_conn, "HOST", [MONDAY], at(TUESDAY, 10), finviz)

    bars, statuses = read_bars(db_conn, "HOST", [MONDAY])
    assert [saved.time for saved in bars] == [at(MONDAY, 4), at(MONDAY, 19, 59)]
    assert statuses == {MONDAY: "complete"}


def test_day_saved_before_8pm_is_partial_then_completed(db_conn):
    save_bar_days(db_conn, "HOST", [MONDAY], at(MONDAY, 11), FakeFinviz([bar(MONDAY, 9, 30)]))
    assert read_bars(db_conn, "HOST", [MONDAY])[1] == {MONDAY: "partial"}

    save_bar_days(db_conn, "HOST", [MONDAY], at(MONDAY, 20, 5), FakeFinviz([bar(MONDAY, 9, 30), bar(MONDAY, 19, 0)]))

    bars, statuses = read_bars(db_conn, "HOST", [MONDAY])
    assert statuses == {MONDAY: "complete"}
    assert len(bars) == 2


def test_complete_days_are_not_fetched_again(db_conn):
    save_bar_days(db_conn, "HOST", [MONDAY], at(TUESDAY, 10), FakeFinviz([bar(MONDAY, 9, 30)]))
    finviz = FakeFinviz([bar(MONDAY, 9, 30)])

    save_bar_days(db_conn, "HOST", [MONDAY], at(TUESDAY, 10), finviz)

    assert finviz.calls == 0


def test_day_older_than_finviz_history_is_missing(db_conn):
    save_bar_days(db_conn, "HOST", [MONDAY], at(date(2026, 11, 30), 10), FakeFinviz([bar(date(2026, 11, 16), 9, 30)]))

    assert read_bars(db_conn, "HOST", [MONDAY]) == ([], {MONDAY: "missing"})


def test_unknown_day_has_no_status(db_conn):
    assert read_bars(db_conn, "HOST", [MONDAY]) == ([], {MONDAY: None})


def test_finviz_error_leaves_nothing_saved_and_warns(db_conn):
    entry = create_entry(db_conn, trade([Fill("buy", at(MONDAY, 10), 2.0, 100)]), at(MONDAY, 10, 5))

    warning = save_bars_for_entry(db_conn, entry, at(MONDAY, 10, 5), FakeFinviz(error=FinvizUnavailableError("1m bars HOST", "timeout")))

    assert warning == BARS_RETRY_WARNING == "Chart bars not saved yet, will retry."
    assert read_bars(db_conn, "HOST", [MONDAY])[1] == {MONDAY: None}


def test_save_bars_for_entry_returns_no_warning_on_success(db_conn):
    entry = create_entry(db_conn, trade([Fill("buy", at(MONDAY, 10), 2.0, 100)]), at(MONDAY, 10, 5))

    assert save_bars_for_entry(db_conn, entry, at(MONDAY, 10, 5), FakeFinviz([bar(MONDAY, 9, 30)])) is None


def test_complete_pending_days_finishes_partial_days(db_conn):
    entry = create_entry(
        db_conn, trade([Fill("buy", at(MONDAY, 10), 2.0, 100), Fill("sell", at(MONDAY, 11), 2.2, 100)]), at(MONDAY, 11)
    )
    save_bars_for_entry(db_conn, entry, at(MONDAY, 11), FakeFinviz([bar(MONDAY, 9, 30)]))

    fetched = complete_pending_days(db_conn, at(MONDAY, 20, 15), FakeFinviz([bar(MONDAY, 9, 30), bar(MONDAY, 19, 0)]))

    assert fetched == 1
    assert read_bars(db_conn, "HOST", [MONDAY])[1] == {MONDAY: "complete"}


def test_complete_pending_days_stops_when_rate_limited(db_conn):
    create_entry(db_conn, trade([Fill("buy", at(MONDAY, 10), 2.0, 100)], ticker="AAA"), at(MONDAY, 11))
    create_entry(db_conn, trade([Fill("buy", at(MONDAY, 10), 2.0, 100)], ticker="BBB"), at(MONDAY, 11))
    finviz = FakeFinviz(error=FinvizRateLimitError("1m bars"))

    assert complete_pending_days(db_conn, at(MONDAY, 21), finviz) == 0
    assert finviz.calls == 1


def test_aggregate_bars_builds_five_minute_bars():
    minute_bars = [
        Bar(at(MONDAY, 9, 30), 2.0, 2.1, 1.9, 2.05, 100),
        Bar(at(MONDAY, 9, 33), 2.05, 2.3, 2.0, 2.2, 200),
        Bar(at(MONDAY, 9, 35), 2.2, 2.25, 2.1, 2.15, 50),
    ]

    five = aggregate_bars(minute_bars, minutes=5)

    assert five == [
        Bar(at(MONDAY, 9, 30), 2.0, 2.3, 1.9, 2.2, 300),
        Bar(at(MONDAY, 9, 35), 2.2, 2.25, 2.1, 2.15, 50),
    ]
