from datetime import date, datetime
from unittest.mock import patch

from app.bars.cache import BarSeries
from app.market_time import EASTERN
from app.patterns.ranking import ScoreBreakdown
from app.patterns.trade_plan import TradePlan
from app.patterns.types import PatternMatch
from app.scanning.scanner import ScanResult
from app.setups.store import mark_ticker_scanned, record_match
from tests.bar_fixtures import daily_bars, minute_bars

NOW = datetime(2026, 10, 20, 10, 0, tzinfo=EASTERN)


def store_setup(conn, ticker="HOST", direction="long", pattern="high_of_day_break", score=70.0):
    sign = 1 if direction == "long" else -1
    match = PatternMatch(pattern=pattern, direction=direction, timeframe="1m", entry=2.0, stop=2.0 - 0.1 * sign,
                         detected_at=NOW, quality=0.7, quality_parts={}, key_points=[(NOW, 2.0)])
    plan = TradePlan(direction=direction, entry=2.0, stop=2.0 - 0.1 * sign, risk_per_share=0.1, risk_percent=5.0,
                     target_3r=2.0 + 0.3 * sign, capped_target=2.0 + 0.15 * sign, available_reward_risk=1.5,
                     blocking_level=2.0 + 0.15 * sign, partial_1r=2.0 + 0.1 * sign, partial_2r=2.0 + 0.2 * sign,
                     trailing_stop=None)
    record_match(conn, ticker, match, plan, "forming", ScoreBreakdown(score, {"reward_risk": 20.0}), "regular", 5.0, NOW)
    mark_ticker_scanned(conn, ticker, NOW)


def fake_load_bars(conn, ticker, interval, now, fetch_bars_fn):
    if interval == "daily":
        return BarSeries(daily_bars([1.8, 1.9, 2.0], start=date(2026, 10, 15)), NOW)
    return BarSeries(minute_bars(9, 30, [2.0, 2.1, 2.2]), NOW)


@patch("app.routes.bars.load_bars", side_effect=fake_load_bars)
def test_bars_route_returns_bars_levels_and_session(mock_load, api_client):
    body = api_client.get("/api/bars/host?interval=1m").json()

    assert len(body["bars"]) == 3
    assert set(body["bars"][0]) == {"time", "open", "high", "low", "close", "volume"}
    # Bars are from Tue Oct 20; the close before that is Mon Oct 19's 2.0.
    assert body["session"]["previous_close"] == 2.0
    assert len(body["vwap"]) == 3
    assert body["daily_levels"] == []
    assert mock_load.call_args_list[0].args[1] == "HOST"


@patch("app.routes.bars.load_bars", side_effect=fake_load_bars)
def test_bars_route_daily_has_no_session(mock_load, api_client):
    body = api_client.get("/api/bars/HOST?interval=daily").json()

    assert body["session"] is None and body["vwap"] is None


def test_bars_route_rejects_unknown_interval(api_client):
    assert api_client.get("/api/bars/HOST?interval=2m").status_code == 422


@patch("app.routes.setups.run_scan", return_value=ScanResult(["HOST"], [("BAD", "Finviz request failed")], 2, NOW))
def test_scan_route_scans_one_ticker(mock_scan, api_client):
    response = api_client.post("/api/scans", json={"ticker": "host"})

    assert response.json() == {
        "scanned": ["HOST"], "failed": [{"ticker": "BAD", "reason": "Finviz request failed"}],
        "setups_found": 2, "scanned_at": "2026-10-20T10:00:00-04:00",
    }
    assert mock_scan.call_args.kwargs["tickers"] == ["HOST"]


@patch("app.routes.setups.run_scan", return_value=ScanResult([], [], 0, NOW))
def test_scan_route_without_ticker_scans_watchlist(mock_scan, api_client):
    api_client.post("/api/scans", json={})

    assert mock_scan.call_args.kwargs["tickers"] is None


def test_setups_hide_shorts_as_warnings_by_default(api_client, db_conn):
    store_setup(db_conn, "LONG", "long")
    store_setup(db_conn, "SHORT", "short", pattern="low_of_day_break")

    body = api_client.get("/api/setups").json()

    assert [setup["ticker"] for setup in body["setups"]] == ["LONG"]
    assert [warning["ticker"] for warning in body["warnings"]] == ["SHORT"]
    assert body["show_short_setups"] is False
    assert body["setups"][0]["blocking_level"] == 2.15


def test_setups_include_shorts_when_setting_on(api_client, db_conn):
    store_setup(db_conn, "SHORT", "short", pattern="low_of_day_break")
    api_client.put("/api/settings", json={"show_short_setups": True})

    body = api_client.get("/api/setups").json()

    assert [setup["direction"] for setup in body["setups"]] == ["short"]
    assert body["warnings"] == []


def test_setups_flag_conflict_when_ticker_has_opposite_record(api_client, db_conn):
    store_setup(db_conn, "HOST", "long")
    store_setup(db_conn, "HOST", "short", pattern="low_of_day_break")

    body = api_client.get("/api/setups").json()

    assert body["setups"][0]["has_conflict"] is True


def test_stock_setups_filter_by_ticker(api_client, db_conn):
    store_setup(db_conn, "HOST")
    store_setup(db_conn, "WORX")

    body = api_client.get("/api/stocks/host/setups").json()

    assert [setup["ticker"] for setup in body["setups"]] == ["HOST"]
