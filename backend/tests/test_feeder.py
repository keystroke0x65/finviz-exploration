from datetime import datetime, timedelta, timezone

import pytest
import responses

from app.config import get_settings
from app.errors import FinvizRateLimitError
from app.finviz_client import ScreenResult, ScreenRow, run_screen
from app.screens.finviz_url import ScreenCriteria
from app.screens.store import ScreenInput, create_screen
from app.watchlist.feeder import is_within_feeder_window, run_feeder
from app.watchlist.store import EASTERN, get_entry, list_entries, record_feeder_hit

NOW = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
RETENTION_DAYS = 90


def _row(ticker: str, change_percent: float | None) -> ScreenRow:
    return ScreenRow(
        ticker=ticker, company=None, country=None, market_cap_millions=None,
        float_millions=None, average_volume_thousands=None, relative_volume=None,
        price=None, change_percent=change_percent, volume=None, after_hours_close=None,
        after_hours_change_percent=None, news_time=None, news_url=None, news_title=None,
    )


def _add_screen(conn, name: str, filters: list[str], feeds_watchlist: bool = True):
    return create_screen(
        conn, ScreenInput(name, ScreenCriteria(filters, None, None), feeds_watchlist), NOW
    )


@pytest.mark.parametrize(
    "eastern_time, expected",
    [
        ("2026-10-20 03:59", False),
        ("2026-10-20 04:00", True),
        ("2026-10-20 19:59", True),
        ("2026-10-20 20:00", False),
        ("2026-10-24 10:00", False),  # Saturday
        ("2026-10-25 10:00", False),  # Sunday
        ("2026-11-02 04:30", True),  # Monday after DST ends (Nov 1, 2026)
        ("2026-11-02 03:30", False),
    ],
)
def test_feeder_window_edges(eastern_time, expected):
    local = datetime.strptime(eastern_time, "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN)

    assert is_within_feeder_window(local.astimezone(timezone.utc)) is expected


def test_run_feeder_adds_hits_from_feeder_screens_only(db_conn):
    _add_screen(db_conn, "Feeder", ["geo_usa"])
    _add_screen(db_conn, "Other", ["sh_price_u5"], feeds_watchlist=False)
    calls = []

    def fake_run_screen(filters, signal, order):
        calls.append(filters)
        return ScreenResult([_row("HOST", 47.4), _row("WORX", 36.6)])

    result = run_feeder(db_conn, fake_run_screen, NOW, RETENTION_DAYS)

    assert calls == [["geo_usa"]]
    assert result.screens_run == 1
    assert result.tickers_added == ["HOST", "WORX"]
    assert result.tickers_updated == []
    assert result.failed_screens == []
    assert get_entry(db_conn, "HOST").appearances[0].change_percent == 47.4


def test_run_feeder_reports_updated_tickers_on_second_run(db_conn):
    _add_screen(db_conn, "Feeder", ["geo_usa"])

    def fake_run_screen(filters, signal, order):
        return ScreenResult([_row("HOST", 47.4)])

    run_feeder(db_conn, fake_run_screen, NOW, RETENTION_DAYS)
    result = run_feeder(db_conn, fake_run_screen, NOW + timedelta(minutes=15), RETENTION_DAYS)

    assert result.tickers_added == []
    assert result.tickers_updated == ["HOST"]


def test_ticker_hit_by_two_feeder_screens_counts_once_as_added(db_conn):
    _add_screen(db_conn, "First", ["geo_usa"])
    _add_screen(db_conn, "Second", ["sh_price_u20"])

    def fake_run_screen(filters, signal, order):
        return ScreenResult([_row("HOST", 47.4)])

    result = run_feeder(db_conn, fake_run_screen, NOW, RETENTION_DAYS)

    assert result.tickers_added == ["HOST"]
    assert result.tickers_updated == []
    assert len(get_entry(db_conn, "HOST").appearances) == 2


def test_run_feeder_continues_after_screen_failure(db_conn):
    _add_screen(db_conn, "First", ["geo_usa"])
    _add_screen(db_conn, "Second", ["sh_price_u20"])

    def fake_run_screen(filters, signal, order):
        if filters == ["geo_usa"]:
            raise FinvizRateLimitError("screen")
        return ScreenResult([_row("WORX", 36.6)])

    result = run_feeder(db_conn, fake_run_screen, NOW, RETENTION_DAYS)

    assert result.screens_run == 2
    assert result.tickers_added == ["WORX"]
    assert len(result.failed_screens) == 1
    screen_name, reason = result.failed_screens[0]
    assert screen_name == "First"
    assert "rate limiting" in reason


def test_run_feeder_expires_stale_entries(db_conn):
    record_feeder_hit(db_conn, "OLD", 5.0, 1, NOW - timedelta(days=100))

    result = run_feeder(db_conn, lambda *args: ScreenResult([]), NOW, RETENTION_DAYS)

    assert result.tickers_expired == ["OLD"]
    assert get_entry(db_conn, "OLD") is None


def test_run_feeder_with_no_feeder_screens_returns_empty_result(db_conn):
    result = run_feeder(db_conn, lambda *args: pytest.fail("should not run"), NOW, RETENTION_DAYS)

    assert result.screens_run == 0
    assert result.tickers_added == []
    assert result.failed_screens == []


@responses.activate
def test_broad_valid_screen_over_5000_rows_still_feeds_watchlist(db_conn, monkeypatch):
    # "US only" legitimately returns ~10,400 rows; size alone must not be
    # treated as "Finviz ignored the filters".
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    get_settings.cache_clear()
    _add_screen(db_conn, "US only", ["geo_usa"])
    header = "Ticker,Change\n"
    body = header + "".join(f"T{index:04d},1.0%\n" for index in range(6000))
    responses.add(responses.GET, "https://elite.finviz.com/export/screener", body=body)

    result = run_feeder(db_conn, run_screen, NOW, RETENTION_DAYS)

    # Not rejected as "unfiltered" (the old bug); capped at the feeder limit instead.
    assert len(result.tickers_added) == 100
    assert result.failed_screens[0][1].startswith("returned 6000 stocks")
    get_settings.cache_clear()


@responses.activate
def test_malformed_finviz_response_fails_only_that_screen(db_conn, monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    get_settings.cache_clear()
    _add_screen(db_conn, "Broken", ["geo_usa"])
    _add_screen(db_conn, "Good", ["sh_price_u20"])
    responses.add(responses.GET, "https://elite.finviz.com/export/screener", body="<html>login</html>")
    responses.add(responses.GET, "https://elite.finviz.com/export/screener", body="Ticker,Change\nHOST,4.0%\n")

    result = run_feeder(db_conn, run_screen, NOW, RETENTION_DAYS)

    assert result.tickers_added == ["HOST"]
    assert [name for name, _ in result.failed_screens] == ["Broken"]
    get_settings.cache_clear()


def test_run_feeder_saves_last_run_summary(db_conn):
    from app.watchlist.run_status import get_last_feeder_run

    _add_screen(db_conn, "First", ["geo_usa"])
    _add_screen(db_conn, "Second", ["sh_price_u20"])

    def fake_run_screen(filters, signal, order):
        if filters == ["geo_usa"]:
            raise FinvizRateLimitError("screen")
        return ScreenResult([_row("WORX", 36.6)])

    assert get_last_feeder_run(db_conn) is None
    run_feeder(db_conn, fake_run_screen, NOW, RETENTION_DAYS)

    last_run = get_last_feeder_run(db_conn)
    assert last_run.finished_at == NOW
    assert last_run.result.tickers_added == ["WORX"]
    assert last_run.result.failed_screens[0][0] == "First"


def test_feeder_caps_hits_per_screen(db_conn):
    from app.watchlist.feeder import MAX_FEEDER_HITS_PER_SCREEN

    _add_screen(db_conn, "Broad", ["geo_usa"])
    rows = [_row(f"T{index:03d}", 1.0) for index in range(150)]

    result = run_feeder(db_conn, lambda *args: ScreenResult(rows), NOW, RETENTION_DAYS)

    assert MAX_FEEDER_HITS_PER_SCREEN == 100
    assert len(result.tickers_added) == 100
    assert result.tickers_added[0] == "T000"
    assert result.failed_screens == [
        ("Broad", "returned 150 stocks; only the first 100 were added — narrow the screen")
    ]
