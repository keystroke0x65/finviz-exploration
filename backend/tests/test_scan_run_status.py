from datetime import datetime, timedelta

import pytest

from app.market_time import EASTERN
from app.scanning.run_status import (
    CompletedScan,
    CrashedScan,
    is_scan_overdue,
    read_scan_status,
    save_scan_attempt,
)

INTERVAL = timedelta(minutes=15)
SCAN_AT = datetime(2026, 10, 26, 15, 0, tzinfo=EASTERN)


def test_no_scan_yet(db_conn):
    status = read_scan_status(db_conn)

    assert (status.latest, status.last_completed_at) == (None, None)


def test_completed_scan_is_the_latest_and_last_completed(db_conn):
    completed = CompletedScan(finished_at=SCAN_AT, scanned=38, failed=[("BAD", "Finviz request failed")])

    save_scan_attempt(db_conn, completed)

    status = read_scan_status(db_conn)
    assert status.latest == completed
    assert status.last_completed_at == SCAN_AT


def test_crash_keeps_the_time_of_the_last_completed_scan(db_conn):
    save_scan_attempt(db_conn, CompletedScan(finished_at=SCAN_AT, scanned=40, failed=[]))
    crash = CrashedScan(finished_at=SCAN_AT + INTERVAL, error_type="TypeError")

    save_scan_attempt(db_conn, crash)

    status = read_scan_status(db_conn)
    assert status.latest == crash
    assert status.last_completed_at == SCAN_AT


@pytest.mark.parametrize("now, last_completed, is_overdue", [
    (datetime(2026, 10, 26, 15, 29, tzinfo=EASTERN), SCAN_AT, False),  # within two intervals
    (datetime(2026, 10, 26, 15, 31, tzinfo=EASTERN), SCAN_AT, True),
    (datetime(2026, 10, 26, 15, 31, tzinfo=EASTERN), None, True),
    (datetime(2026, 10, 26, 20, 30, tzinfo=EASTERN), SCAN_AT, False),  # scans stop at 8 PM
    (datetime(2026, 10, 24, 12, 0, tzinfo=EASTERN), SCAN_AT, False),  # Saturday
    # Just after 4 AM yesterday's last scan is old, but today's first one isn't due yet.
    (datetime(2026, 10, 27, 4, 20, tzinfo=EASTERN), SCAN_AT, False),
    (datetime(2026, 10, 27, 4, 31, tzinfo=EASTERN), SCAN_AT, True),
])
def test_scan_is_overdue_after_two_missed_intervals_during_scan_hours(now, last_completed, is_overdue):
    assert is_scan_overdue(last_completed, now, INTERVAL) is is_overdue
