from datetime import date, datetime

import pytest

from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.market_time import EASTERN
from app.scanning.scanner import ScanDeps, run_scan, scan_ticker
from app.scanning.snapshots import read_snapshots
from app.setups.store import list_current_setups
from app.watchlist.store import add_manual_entry
from tests.bar_fixtures import TRADING_DAY, daily_bars, minute_bars
from tests.scan_fixtures import snapshot

NOW = datetime(2026, 10, 20, 9, 44, tzinfo=EASTERN)
HOD_BREAK_CLOSES = [2.0, 2.1, 2.2, 2.3, 2.4, 2.45, 2.4, 2.35, 2.3, 2.35, 2.4, 2.44, 2.47, 2.52]
LOD_BREAK_CLOSES = [3.0, 2.9, 2.8, 2.7, 2.6, 2.55, 2.6, 2.65, 2.7, 2.65, 2.6, 2.56, 2.53, 2.48]


def bars_for(closes):
    def fetch_bars(ticker, interval):
        if interval == "daily":
            return daily_bars([1.5, 1.8, 2.0], start=date(2026, 10, 15))
        return minute_bars(9, 30, closes)
    return fetch_bars


def deps(fetch_bars=None, failing=None, auth_failing=None, rate_limited=None):
    def fetch(ticker, interval):
        if ticker == rate_limited:
            raise FinvizRateLimitError(f"{interval} bars {ticker}")
        if ticker == failing:
            raise FinvizUnavailableError(f"{interval} bars {ticker}", "ReadTimeout")
        if ticker == auth_failing:
            raise FinvizAuthError()
        return (fetch_bars or bars_for(HOD_BREAK_CLOSES))(ticker, interval)

    return ScanDeps(fetch_bars=fetch, fetch_snapshots=lambda tickers: [snapshot(t, relative_volume=3.0) for t in tickers])


def test_scan_ticker_records_detected_setup(db_conn):
    found = scan_ticker(db_conn, "HOST", snapshot("HOST", relative_volume=3.0), NOW, deps())

    setups = list_current_setups(db_conn, "HOST")
    hod = [setup for setup in setups if setup.pattern == "high_of_day_break" and setup.timeframe == "1m"]
    assert found >= 1
    assert len(hod) == 1
    assert hod[0].entry == pytest.approx(2.46)
    assert hod[0].session == "regular"
    assert hod[0].float_at_detection == 5.0
    assert hod[0].score > 0


def test_scan_ticker_records_short_matches_too(db_conn):
    scan_ticker(db_conn, "DOWN", snapshot("DOWN"), NOW, deps(bars_for(LOD_BREAK_CLOSES)))

    assert any(setup.direction == "short" for setup in list_current_setups(db_conn, "DOWN"))


def test_run_scan_continues_after_ticker_failure(db_conn):
    result = run_scan(db_conn, NOW, deps(failing="BBB"), tickers=["AAA", "BBB", "CCC"])

    assert result.scanned == ["AAA", "CCC"]
    assert result.failed == [("BBB", "Finviz request failed (daily bars BBB): ReadTimeout")]


def test_run_scan_stops_after_auth_failure(db_conn):
    result = run_scan(db_conn, NOW, deps(auth_failing="AAA"), tickers=["AAA", "BBB"])

    assert result.scanned == []
    assert [ticker for ticker, _ in result.failed] == ["AAA"]


def test_run_scan_saves_watchlist_snapshots(db_conn):
    add_manual_entry(db_conn, "HOST", NOW)

    result = run_scan(db_conn, NOW, deps())

    stored_row, fetched_at = read_snapshots(db_conn)["HOST"]
    assert stored_row.relative_volume == 3.0
    assert fetched_at == NOW
    assert result.scanned == ["HOST"]  # rel vol 3.0 makes it active


def test_run_scan_reports_snapshot_failure(db_conn):
    add_manual_entry(db_conn, "HOST", NOW)

    def broken_snapshots(tickers):
        raise FinvizUnavailableError("snapshot", "HTTP 500")

    result = run_scan(db_conn, NOW, ScanDeps(fetch_bars=bars_for(HOD_BREAK_CLOSES), fetch_snapshots=broken_snapshots))

    assert result.scanned == []
    assert result.failed == [("watchlist prices", "Finviz request failed (snapshot): HTTP 500")]


def test_run_scan_backs_off_after_rate_limit(db_conn):
    # Every further request would also be refused; stop and say what was skipped.
    result = run_scan(db_conn, NOW, deps(rate_limited="BBB"), tickers=["AAA", "BBB", "CCC", "DDD"])

    assert result.scanned == ["AAA"]
    assert result.failed[0] == ("BBB", "Finviz is rate limiting requests (daily bars BBB); try again in a minute.")
    assert result.failed[1] == ("CCC, DDD", "skipped: Finviz is rate limiting requests")
