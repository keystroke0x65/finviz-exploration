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


def test_redetection_keeps_original_plan_and_refreshes_state(db_conn):
    first = record(db_conn, now=SCAN_1, state="forming")
    changed_plan = TradePlan(direction="long", entry=2.0, stop=1.8, risk_per_share=0.2, risk_percent=10.0,
                             target_3r=2.6, capped_target=2.6, available_reward_risk=3.0, blocking_level=None,
                             partial_1r=2.2, partial_2r=2.4, trailing_stop=None)

    second = record_match(db_conn, "HOST", match(), changed_plan, "triggered", SCORE, "regular", 5.46, SCAN_2)

    assert second.id == first.id
    assert (second.stop, second.capped_target) == (1.9, 2.15)  # plan as first detected
    assert second.state == "triggered"
    assert second.first_state == "forming"


def test_resolved_record_is_not_reused_by_a_new_detection(db_conn):
    first = record(db_conn, now=SCAN_1)
    save_outcome(db_conn, first.id, Resolution("stop", SCAN_2, 0.5, -1.0))

    second = record(db_conn, now=SCAN_2 + timedelta(days=7), state="forming")

    assert second.id != first.id
    assert second.outcome == "open"
    outcomes = [row[0] for row in db_conn.execute("SELECT outcome FROM setup_records ORDER BY id")]
    assert outcomes == ["stop", "open"]


def test_list_current_setups_drops_tickers_not_scanned_recently(db_conn):
    record(db_conn, now=SCAN_1)  # HOST, scanned at SCAN_1
    other = PatternMatch(pattern="bull_flag", direction="long", timeframe="1m", entry=3.0, stop=2.9,
                         detected_at=DETECTED, quality=0.7, quality_parts={}, key_points=[])
    days_later = SCAN_1 + timedelta(days=3)
    record_match(db_conn, "WORX", other, plan(3.0), "forming", SCORE, "regular", 1.0, days_later)
    mark_ticker_scanned(db_conn, "WORX", days_later)

    assert [setup.ticker for setup in list_current_setups(db_conn)] == ["WORX"]


def test_setup_keeps_verdict_from_first_detection(db_conn):
    first = record_match(db_conn, "HOST", match(), plan(), "forming", SCORE, "regular", 5.0, SCAN_1,
                         verdict="leans_long")
    second = record_match(db_conn, "HOST", match(), plan(), "forming", SCORE, "regular", 5.0, SCAN_2,
                          verdict="leans_short")

    assert first.verdict == second.verdict == "leans_long"


def test_record_match_stores_and_refreshes_the_trigger_time(db_conn):
    first_cross = datetime(2026, 10, 20, 9, 42, tzinfo=EASTERN)
    later_cross = datetime(2026, 10, 20, 9, 51, tzinfo=EASTERN)

    triggered = record_match(db_conn, "HOST", match(), plan(), "triggered", SCORE, "regular", 5.46, SCAN_1,
                             triggered_at=first_cross)
    assert triggered.triggered_at == first_cross

    retriggered = record_match(db_conn, "HOST", match(), plan(), "triggered", SCORE, "regular", 5.46, SCAN_2,
                               triggered_at=later_cross)
    assert retriggered.triggered_at == later_cross

    back_to_forming = record_match(db_conn, "HOST", match(), plan(), "forming", SCORE, "regular", 5.46, SCAN_2)
    assert back_to_forming.triggered_at is None


def test_record_match_stores_and_refreshes_the_sliding_scale(db_conn):
    from app.patterns.sliding_scale import Factor, SlidingScale

    first_grade = SlidingScale(letter="C", points=8, factors=[Factor("Time", "poor", "Pre-market (7:05 AM)")])
    later_grade = SlidingScale(letter="B", points=10, factors=[Factor("Time", "good", "Power hour (9:45 AM)")])
    record_match(db_conn, "HOST", match(), plan(), "forming", SCORE, "regular", 5.0, SCAN_1, sliding_scale=first_grade)

    refreshed = record_match(
        db_conn, "HOST", match(), plan(), "triggered", SCORE, "regular", 5.0, SCAN_2, sliding_scale=later_grade
    )

    assert refreshed.sliding_scale == later_grade


def test_records_without_a_sliding_scale_read_back_as_none(db_conn):
    assert record(db_conn).sliding_scale is None
