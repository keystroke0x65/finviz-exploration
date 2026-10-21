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
    assert [ticker for ticker, _ in result.failed] == ["AAA", "BBB"]  # BBB listed as skipped


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


def test_scan_ignores_intraday_bars_from_an_earlier_day(db_conn):
    # 4:00 AM scans see yesterday's movers with only yesterday's bars.
    yesterday = date(2026, 10, 19)

    def yesterday_only(ticker, interval):
        if interval == "daily":
            return daily_bars([1.5, 1.8], start=date(2026, 10, 15))
        return minute_bars(9, 30, HOD_BREAK_CLOSES, day=yesterday)

    early_morning = datetime(2026, 10, 20, 7, 0, tzinfo=EASTERN)
    scan_ticker(db_conn, "HOST", None, early_morning, deps(yesterday_only))

    assert [setup for setup in list_current_setups(db_conn, "HOST") if setup.timeframe != "daily"] == []


def test_unexpected_error_on_one_ticker_does_not_stop_the_scan(db_conn):
    def broken_for_bbb(ticker, interval):
        if ticker == "BBB":
            raise KeyError("Open")
        return bars_for(HOD_BREAK_CLOSES)(ticker, interval)

    result = run_scan(db_conn, NOW, deps(broken_for_bbb), tickers=["AAA", "BBB", "CCC"])

    assert result.scanned == ["AAA", "CCC"]
    assert result.failed == [("BBB", "internal error (KeyError); see backend logs")]


def test_scan_resolves_open_setups_of_tickers_no_longer_active(db_conn):
    from app.setups.store import list_open_records

    # Just below the high of day: a forming setup that stays open.
    forming = bars_for(HOD_BREAK_CLOSES[:-3] + [2.42, 2.43, 2.44])
    scan_ticker(db_conn, "HOST", snapshot("HOST"), NOW, deps(forming))
    assert list_open_records(db_conn, "HOST") != []

    after_close = datetime(2026, 10, 20, 20, 30, tzinfo=EASTERN)
    run_scan(db_conn, after_close, deps(forming), tickers=["OTHER"])

    assert list_open_records(db_conn, "HOST") == []


def test_scan_ticker_saves_verdict(db_conn):
    from app.scanning.verdicts import read_verdicts

    scan_ticker(db_conn, "HOST", snapshot("HOST"), NOW, deps())

    verdict, computed_at = read_verdicts(db_conn)["HOST"]
    assert verdict.call in {"leans_long", "leans_short", "no_clear_edge"}
    assert verdict.reasons
    assert computed_at == NOW
    assert all(setup.verdict == verdict.call for setup in list_current_setups(db_conn, "HOST"))


def test_verdict_counts_only_patterns_that_became_setups(db_conn):
    import re

    from app.scanning.verdicts import read_verdicts
    from tests.pattern_shapes import shape

    # A tight ascending triangle (top 2.50, latest swing low ~2.449) with the last
    # close already under that stop: detected, but invalidated, so not a setup.
    from tests.test_triangle_detectors import HIGHS, LOWS

    def tighten(prices):
        return [2.50 + (price - 2.50) * 0.3 for price in prices]

    invalidated = shape(tighten(HIGHS), tighten(LOWS), last_close=2.44)

    def fetch(ticker, interval):
        if interval == "daily":
            return daily_bars([2.0, 2.1], start=date(2026, 10, 15))
        return invalidated

    scan_ticker(db_conn, "HOST", None, NOW, deps(fetch))

    verdict, _ = read_verdicts(db_conn)["HOST"]
    counted = sum(int(n) for n in re.findall(r"(\d+) (?:bullish|bearish)", " ".join(verdict.reasons)))
    assert counted == len(list_current_setups(db_conn, "HOST"))


def test_daily_setup_state_uses_todays_intraday_price(db_conn):
    # Daily bull flag (pole ~1.00 -> 1.30, flag 1.26-1.31) whose cached daily close
    # still looks fine, while today's 1m bars have already broken below the flag.
    daily = daily_bars([1.0, 1.0, 1.06, 1.12, 1.18, 1.24, 1.30, 1.28, 1.27, 1.27, 1.28], start=date(2026, 10, 5),
                       spread=0.01)

    def fetch(ticker, interval):
        if interval == "daily":
            return daily
        return minute_bars(9, 30, [1.27, 1.25, 1.22, 1.20, 1.18, 1.17, 1.16, 1.15], spread=0.005)

    scan_ticker(db_conn, "HOST", None, NOW, deps(fetch))

    daily_flags = [s for s in list_current_setups(db_conn, "HOST") if s.timeframe == "daily" and s.pattern == "bull_flag"]
    assert daily_flags == []


def test_run_scan_lists_skipped_tickers_after_auth_failure(db_conn):
    result = run_scan(db_conn, NOW, deps(auth_failing="AAA"), tickers=["AAA", "BBB", "CCC"])

    assert result.failed[1] == ("BBB, CCC", "skipped: Finviz rejected the auth token")
