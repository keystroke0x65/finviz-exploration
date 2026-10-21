from datetime import datetime, timedelta

from app.market_time import EASTERN
from app.patterns.ranking import ScoreBreakdown
from app.patterns.trade_plan import TradePlan
from app.patterns.types import PatternMatch
from app.setups.resolver import Resolution
from app.setups.store import (
    list_current_setups,
    list_open_records,
    mark_ticker_scanned,
    record_match,
    save_outcome,
)

DETECTED = datetime(2026, 10, 20, 10, 0, tzinfo=EASTERN)
SCAN_1 = DETECTED + timedelta(seconds=30)
SCAN_2 = SCAN_1 + timedelta(minutes=15)
SCORE = ScoreBreakdown(total=72.5, parts={"reward_risk": 40.0, "conflict": 0.0})


def match(entry=2.0, pattern="bull_flag", direction="long"):
    return PatternMatch(pattern=pattern, direction=direction, timeframe="1m", entry=entry,
                        stop=1.9 if direction == "long" else 2.1, detected_at=DETECTED, quality=0.7,
                        quality_parts={"pole_strength": 0.7}, key_points=[(DETECTED, 2.0)])


def plan(entry=2.0):
    return TradePlan(direction="long", entry=entry, stop=1.9, risk_per_share=0.1, risk_percent=5.0, target_3r=2.3,
                     capped_target=2.15, available_reward_risk=1.5, blocking_level=2.15, partial_1r=2.1,
                     partial_2r=2.2, trailing_stop=1.95)


def record(conn, now=SCAN_1, state="forming", entry=2.0, **kwargs):
    saved = record_match(conn, "HOST", match(entry=entry, **kwargs), plan(entry), state, SCORE, "regular", 5.46, now)
    mark_ticker_scanned(conn, "HOST", now)
    return saved


def test_record_match_stores_plan_and_score(db_conn):
    saved = record(db_conn)

    assert saved.capped_target == 2.15
    assert saved.blocking_level == 2.15
    assert saved.score == 72.5
    assert saved.score_parts == {"reward_risk": 40.0, "conflict": 0.0}
    assert saved.key_points == [(DETECTED, 2.0)]
    assert saved.outcome == "open"
    assert saved.float_at_detection == 5.46


def test_record_match_twice_updates_existing_record(db_conn):
    first = record(db_conn, now=SCAN_1, state="forming")
    second = record(db_conn, now=SCAN_2, state="triggered")

    assert second.id == first.id
    assert second.state == "triggered"
    assert second.detected_at == DETECTED
    assert second.last_seen_at == SCAN_2
    assert db_conn.execute("SELECT COUNT(*) FROM setup_records").fetchone()[0] == 1


def test_entry_rounding_dedupes_float_noise(db_conn):
    record(db_conn, entry=2.0)
    record(db_conn, entry=2.00000001)

    assert db_conn.execute("SELECT COUNT(*) FROM setup_records").fetchone()[0] == 1


def test_list_current_setups_only_latest_scan(db_conn):
    record(db_conn, now=SCAN_1, pattern="bull_flag")
    record(db_conn, now=SCAN_2, pattern="flat_top_breakout")

    assert [setup.pattern for setup in list_current_setups(db_conn)] == ["flat_top_breakout"]


def test_list_current_setups_excludes_invalidated(db_conn):
    record(db_conn, state="invalidated")

    assert list_current_setups(db_conn) == []


def test_list_current_setups_filters_by_ticker(db_conn):
    record(db_conn)

    assert list_current_setups(db_conn, "OTHER") == []
    assert len(list_current_setups(db_conn, "HOST")) == 1


def test_save_outcome_closes_record(db_conn):
    saved = record(db_conn)

    save_outcome(db_conn, saved.id, Resolution("target", SCAN_2, 3.0, -0.2))

    assert list_open_records(db_conn, "HOST") == []
