from dataclasses import replace
from datetime import datetime, timedelta

from app.journal.setup_matching import match_setups
from app.market_time import EASTERN
from tests.test_setup_store import record

ENTRY_TIME = datetime(2026, 11, 16, 9, 45, tzinfo=EASTERN)


def at(minutes):
    return ENTRY_TIME + timedelta(minutes=minutes)


def setup(db_conn, setup_id, **changes):
    base = record(db_conn)
    defaults = {"id": setup_id, "pattern": "bull_flag", "timeframe": "5m", "direction": "long", "entry": 0.76,
                "detected_at": at(-20), "outcome": "open", "resolved_at": None, "triggered_at": at(-1), "score": 80.0}
    return replace(base, **{**defaults, **changes})


def ids(records):
    return [item.id for item in records]


def test_matches_only_setups_live_at_the_entry_in_the_trades_direction(db_conn):
    live = setup(db_conn, 1)
    short = setup(db_conn, 2, direction="short")
    later = setup(db_conn, 3, pattern="flat_top_breakout", detected_at=at(5))
    stopped_before = setup(db_conn, 4, pattern="red_to_green", outcome="stop", resolved_at=at(-5))
    stopped_after = setup(db_conn, 5, pattern="abcd", outcome="stop", resolved_at=at(10))

    matches, others = match_setups([live, short, later, stopped_before, stopped_after], ENTRY_TIME, "long", 0.76)

    assert ids(matches) == [1, 5]
    assert sorted(ids(others)) == [2, 3, 4]


def test_copies_of_one_setup_show_once(db_conn):
    first = setup(db_conn, 1, detected_at=at(-60), outcome="expired", resolved_at=at(-30))
    again = setup(db_conn, 2, detected_at=at(-20))

    matches, others = match_setups([first, again], ENTRY_TIME, "long", 0.76)

    assert ids(matches) == [2]
    assert ids(others) == []


def test_ranks_by_entry_closeness_then_trigger_time_then_score(db_conn):
    far = setup(db_conn, 1, pattern="abcd", entry=0.90, score=99.0)
    close_late_trigger = setup(db_conn, 2, pattern="red_to_green", entry=0.75, triggered_at=at(-30))
    close_recent_trigger = setup(db_conn, 3, pattern="flat_top_breakout", entry=0.75, triggered_at=at(-2))
    forming = setup(db_conn, 4, pattern="bull_pennant", entry=0.75, triggered_at=None)

    matches, _ = match_setups([far, close_late_trigger, close_recent_trigger, forming], ENTRY_TIME, "long", 0.76)

    assert ids(matches) == [3, 2, 4, 1]


def test_without_direction_or_price_any_live_setup_matches_best_score_first(db_conn):
    long_setup = setup(db_conn, 1, score=70.0)
    short_setup = setup(db_conn, 2, pattern="bear_flag", direction="short", score=90.0)

    matches, _ = match_setups([long_setup, short_setup], ENTRY_TIME, None, None)

    assert ids(matches) == [2, 1]


def test_others_are_deduped_and_best_score_first(db_conn):
    later_low = setup(db_conn, 1, pattern="abcd", detected_at=at(5), score=40.0)
    later_high = setup(db_conn, 2, pattern="bear_flag", direction="short", detected_at=at(6), score=90.0)

    _, others = match_setups([later_low, later_high], ENTRY_TIME, "long", 0.76)

    assert ids(others) == [2, 1]


def test_a_setup_first_seen_past_its_entry_is_still_live(db_conn):
    # not_tracked is bookkeeping for the track record, not the setup ending.
    seen_late = setup(db_conn, 1, outcome="not_tracked", resolved_at=at(-20))

    matches, _ = match_setups([seen_late], ENTRY_TIME, "long", 0.76)

    assert ids(matches) == [1]
