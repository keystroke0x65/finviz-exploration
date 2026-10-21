import pytest

from app.setups.track_record import classify_float, compute_track_record, stats_for

DETECTED = "2026-10-20T10:00:00-04:00"


def add_record(conn, outcome, pattern="bull_flag", timeframe="1m", available_rr=3.0, filled=True,
               float_millions=5.0, session="regular", entry=None):
    entry = entry if entry is not None else 2.0 + conn.execute("SELECT COUNT(*) FROM setup_records").fetchone()[0] / 100
    conn.execute(
        """
        INSERT INTO setup_records (ticker, pattern, direction, timeframe, entry, stop, capped_target, target_3r,
            available_reward_risk, risk_percent, partial_1r, partial_2r, quality, score, score_parts, key_points,
            state, first_state, session, float_at_detection, detected_at, last_seen_at, outcome, max_favorable_r,
            max_adverse_r)
        VALUES ('HOST', ?, 'long', ?, ?, ?, ?, ?, ?, 5, 0, 0, 0.7, 70, '{}', '[]', 'forming', 'forming', ?, ?, ?, ?, ?, ?, ?)
        """,
        (pattern, timeframe, entry, entry - 0.1, entry + 0.1 * available_rr, entry + 0.3, available_rr, session,
         float_millions, DETECTED, DETECTED, outcome, 1.5 if filled else None, -0.5 if filled else None),
    )
    conn.commit()


def test_win_rate_and_average_r(db_conn):
    add_record(db_conn, "target", available_rr=3.0)
    add_record(db_conn, "target", available_rr=1.5)
    add_record(db_conn, "stop")
    add_record(db_conn, "expired", filled=True)

    [stats] = compute_track_record(db_conn)

    assert (stats.pattern, stats.timeframe) == ("bull_flag", "1m")
    assert (stats.trades, stats.wins, stats.losses, stats.expired_after_fill) == (4, 2, 1, 1)
    assert stats.win_rate == pytest.approx(0.5)
    assert stats.average_r == pytest.approx((3.0 + 1.5 - 1 + 0) / 4)
    assert stats.average_max_favorable_r == pytest.approx(1.5)


def test_unfilled_and_untracked_setups_are_not_trades(db_conn):
    add_record(db_conn, "target")
    add_record(db_conn, "expired", filled=False)
    add_record(db_conn, "not_tracked", filled=False)
    add_record(db_conn, "unresolved", filled=False)
    add_record(db_conn, "open", filled=False)

    [stats] = compute_track_record(db_conn)

    assert stats.trades == 1
    assert stats.win_rate == 1.0
    assert stats.not_trades == 3
    assert stats.still_open == 1


def test_groups_by_pattern_and_timeframe_most_trades_first(db_conn):
    add_record(db_conn, "target", pattern="abcd", timeframe="5m")
    add_record(db_conn, "stop", pattern="bull_flag")
    add_record(db_conn, "stop", pattern="bull_flag")

    rows = compute_track_record(db_conn)

    assert [(row.pattern, row.trades) for row in rows] == [("bull_flag", 2), ("abcd", 1)]


def test_filters_by_float_bucket_and_session(db_conn):
    add_record(db_conn, "target", float_millions=3.0, session="pre-market")
    add_record(db_conn, "stop", float_millions=30.0, session="regular")

    assert [row.wins for row in compute_track_record(db_conn, float_bucket="under_5m")] == [1]
    assert [row.losses for row in compute_track_record(db_conn, session="regular")] == [1]
    assert compute_track_record(db_conn, timeframe="daily") == []


def test_pattern_with_only_non_trades_has_no_rates(db_conn):
    add_record(db_conn, "open", filled=False)

    [stats] = compute_track_record(db_conn)

    assert stats.trades == 0
    assert stats.win_rate is None and stats.average_r is None


def test_stats_for_one_pattern(db_conn):
    add_record(db_conn, "target", pattern="abcd", timeframe="5m")

    assert stats_for(db_conn, "abcd", "5m").trades == 1
    assert stats_for(db_conn, "abcd", "1m") is None


@pytest.mark.parametrize("value, bucket", [
    (None, "unknown"), (4.99, "under_5m"), (5.0, "5m_to_10m"), (10.0, "10m_to_20m"), (20.0, "20m_to_50m"),
    (50.0, "over_50m"),
])
def test_float_bucket_boundaries(value, bucket):
    assert classify_float(value) == bucket
