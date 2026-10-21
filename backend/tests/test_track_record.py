import pytest

from app.setups.track_record import classify_float, compute_track_record, has_enough_history, stats_for

DETECTED = "2026-10-20T10:00:00-04:00"


def add_record(conn, outcome, pattern="bull_flag", timeframe="1m", available_rr=3.0, filled=True,
               float_millions=5.0, session="regular", entry=None, ticker="HOST", detected_at=DETECTED,
               resolved_at=None):
    count = conn.execute("SELECT COUNT(*) FROM setup_records").fetchone()[0]
    entry = entry if entry is not None else 2.0 + count / 100
    # Each record exits on its own bar unless a test says otherwise.
    if resolved_at is None and outcome in ("target", "stop", "expired"):
        resolved_at = f"2026-10-20T11:{count:02d}:00-04:00"
    conn.execute(
        """
        INSERT INTO setup_records (ticker, pattern, direction, timeframe, entry, stop, capped_target, target_3r,
            available_reward_risk, risk_percent, partial_1r, partial_2r, quality, score, score_parts, key_points,
            state, first_state, session, float_at_detection, detected_at, last_seen_at, outcome, resolved_at,
            max_favorable_r, max_adverse_r)
        VALUES (?, ?, 'long', ?, ?, ?, ?, ?, ?, 5, 0, 0, 0.7, 70, '{}', '[]', 'forming', 'forming', ?, ?, ?, ?, ?, ?,
            ?, ?)
        """,
        (ticker, pattern, timeframe, entry, entry - 0.1, entry + 0.1 * available_rr, entry + 0.3, available_rr,
         session, float_millions, detected_at, detected_at, outcome, resolved_at, 1.5 if filled else None,
         -0.5 if filled else None),
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


def test_one_trade_detected_twice_counts_once(db_conn):
    # Two records of the same pattern on one ticker that exit on the same bar are one trade
    # (e.g. re-detected with a nudged entry), so they mustn't double the sample.
    exit_bar = "2026-10-20T11:30:00-04:00"
    add_record(db_conn, "target", entry=2.00, resolved_at=exit_bar)
    add_record(db_conn, "target", entry=2.01, resolved_at=exit_bar)
    add_record(db_conn, "target", ticker="OTHER", resolved_at=exit_bar)
    add_record(db_conn, "stop")

    [stats] = compute_track_record(db_conn)

    assert (stats.trades, stats.wins, stats.losses) == (3, 2, 1)


def test_reports_tickers_trading_days_and_date_span(db_conn):
    add_record(db_conn, "target", ticker="AAA", detected_at="2026-10-14T09:45:00-04:00")
    add_record(db_conn, "stop", ticker="AAA", detected_at="2026-10-20T15:00:00-04:00")
    add_record(db_conn, "stop", ticker="BBB", detected_at="2026-10-20T19:30:00-04:00")
    add_record(db_conn, "open", ticker="CCC", filled=False, detected_at="2026-10-21T10:00:00-04:00")

    [stats] = compute_track_record(db_conn)

    assert (stats.tickers, stats.trading_days) == (2, 2)
    assert (stats.first_day, stats.last_day) == ("2026-10-14", "2026-10-20")


def test_average_win_shows_how_big_the_wins_were(db_conn):
    add_record(db_conn, "target", available_rr=0.5)
    add_record(db_conn, "target", available_rr=1.5)
    add_record(db_conn, "stop")

    [stats] = compute_track_record(db_conn)

    assert stats.average_win_r == pytest.approx(1.0)


def test_average_win_is_none_without_wins(db_conn):
    add_record(db_conn, "stop")

    [stats] = compute_track_record(db_conn)

    assert stats.average_win_r is None


def _record_trades(conn, count, days):
    for index in range(count):
        day = 10 + index % days
        add_record(conn, "stop", ticker=f"T{index}", detected_at=f"2026-09-{day:02d}T10:00:00-04:00",
                   resolved_at=f"2026-09-{day:02d}T11:00:00-04:00")


def test_enough_history_needs_thirty_trades_over_five_trading_days(db_conn):
    _record_trades(db_conn, 30, days=5)

    assert has_enough_history(stats_for(db_conn, "bull_flag", "1m"))


def test_thirty_trades_from_too_few_days_is_not_enough_history(db_conn):
    _record_trades(db_conn, 40, days=4)

    assert not has_enough_history(stats_for(db_conn, "bull_flag", "1m"))


def test_twenty_nine_trades_is_not_enough_history(db_conn):
    _record_trades(db_conn, 29, days=10)

    assert not has_enough_history(stats_for(db_conn, "bull_flag", "1m"))
