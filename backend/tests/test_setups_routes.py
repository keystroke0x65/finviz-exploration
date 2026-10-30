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


def store_setup(conn, ticker="HOST", direction="long", pattern="high_of_day_break", score=70.0, state="forming",
                triggered_at=None, sliding_scale=None):
    sign = 1 if direction == "long" else -1
    match = PatternMatch(pattern=pattern, direction=direction, timeframe="1m", entry=2.0, stop=2.0 - 0.1 * sign,
                         detected_at=NOW, quality=0.7, quality_parts={}, key_points=[(NOW, 2.0)])
    plan = TradePlan(direction=direction, entry=2.0, stop=2.0 - 0.1 * sign, risk_per_share=0.1, risk_percent=5.0,
                     target_3r=2.0 + 0.3 * sign, capped_target=2.0 + 0.15 * sign, available_reward_risk=1.5,
                     blocking_level=2.0 + 0.15 * sign, partial_1r=2.0 + 0.1 * sign, partial_2r=2.0 + 0.2 * sign,
                     trailing_stop=None)
    record_match(conn, ticker, match, plan, state, ScoreBreakdown(score, {"reward_risk": 20.0}), "regular", 5.0, NOW,
                 triggered_at=triggered_at, sliding_scale=sliding_scale)
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
    # Someone asking to scan one stock now wants its latest bars, not cached ones.
    assert mock_scan.call_args.kwargs["should_refresh_intraday"] is True


@patch("app.routes.setups.run_scan", return_value=ScanResult([], [], 0, NOW))
def test_scan_route_without_ticker_scans_watchlist(mock_scan, api_client):
    api_client.post("/api/scans", json={})

    assert mock_scan.call_args.kwargs["tickers"] is None
    assert mock_scan.call_args.kwargs["should_refresh_intraday"] is False


@patch("app.routes.setups.run_scan", return_value=ScanResult(["HOST", "WORX"], [("BAD", "rate limited")], 2, NOW))
def test_full_scan_from_the_page_is_recorded(mock_scan, api_client):
    api_client.post("/api/scans", json={})

    status = api_client.get("/api/scans/status").json()

    assert status["latest"] == {
        "status": "completed", "finished_at": "2026-10-20T10:00:00-04:00", "scanned": 2,
        "failed": [{"ticker": "BAD", "reason": "rate limited"}],
    }
    assert status["last_completed_at"] == "2026-10-20T10:00:00-04:00"


@patch("app.routes.setups.run_scan", return_value=ScanResult(["HOST"], [], 1, NOW))
def test_one_stock_scan_is_not_recorded_as_the_last_scan(mock_scan, api_client):
    api_client.post("/api/scans", json={"ticker": "HOST"})

    assert api_client.get("/api/scans/status").json()["latest"] is None


def test_scan_status_reports_a_crash_and_whether_scans_are_overdue(api_client, db_conn):
    from app.scanning.run_status import CrashedScan, save_scan_attempt

    save_scan_attempt(db_conn, CrashedScan(finished_at=NOW, error_type="TypeError"))

    status = api_client.get("/api/scans/status").json()

    assert status["latest"] == {"status": "crashed", "finished_at": "2026-10-20T10:00:00-04:00", "error_type": "TypeError"}
    assert status["last_completed_at"] is None
    assert isinstance(status["is_overdue"], bool)


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


def test_bearish_pattern_on_lower_timeframe_is_not_a_conflict(api_client, db_conn):
    from app.patterns.ranking import ScoreBreakdown as Breakdown

    long_match = PatternMatch(pattern="bull_flag", direction="long", timeframe="5m", entry=2.0, stop=1.9,
                              detected_at=NOW, quality=0.7, quality_parts={}, key_points=[])
    long_plan = TradePlan(direction="long", entry=2.0, stop=1.9, risk_per_share=0.1, risk_percent=5.0,
                          target_3r=2.3, capped_target=2.3, available_reward_risk=3.0, blocking_level=None,
                          partial_1r=2.1, partial_2r=2.2, trailing_stop=None)
    record_match(db_conn, "HOST", long_match, long_plan, "forming", Breakdown(70.0, {}), "regular", 5.0, NOW)
    store_setup(db_conn, "HOST", "short", pattern="bear_flag")  # 1m, lower than 5m

    body = api_client.get("/api/setups").json()

    assert body["setups"][0]["has_conflict"] is False


def test_stock_verdict_route(api_client, db_conn):
    from app.patterns.verdict import Verdict
    from app.scanning.verdicts import save_verdict

    save_verdict(db_conn, "HOST", Verdict("leans_long", 0.41, {"trend": 1.0}, ["Above 5 of 5 trend lines"]), NOW)

    body = api_client.get("/api/stocks/host/verdict").json()

    assert body["call"] == "leans_long"
    assert body["reasons"] == ["Above 5 of 5 trend lines"]
    assert api_client.get("/api/stocks/WORX/verdict").json() is None


def test_setups_include_ticker_verdict(api_client, db_conn):
    from app.patterns.verdict import Verdict
    from app.scanning.verdicts import save_verdict

    store_setup(db_conn, "HOST")
    save_verdict(db_conn, "HOST", Verdict("no_clear_edge", 0.05, {}, ["Volume balanced"]), NOW)

    setup = api_client.get("/api/setups").json()["setups"][0]

    assert setup["verdict"]["call"] == "no_clear_edge"


def test_second_scan_request_gets_409(api_client):
    from app.scanning.lock import scan_lock

    assert scan_lock.acquire(blocking=False)
    try:
        response = api_client.post("/api/scans", json={})
    finally:
        scan_lock.release()

    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_scan_lock_released_after_error(api_client):
    import pytest

    from app.scanning.lock import scan_lock

    with patch("app.routes.setups.run_scan", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            api_client.post("/api/scans", json={})

    assert scan_lock.acquire(blocking=False)
    scan_lock.release()


def test_warnings_do_not_include_short_trade_plans(api_client, db_conn):
    store_setup(db_conn, "SHORT", "short", pattern="low_of_day_break")

    warning = api_client.get("/api/setups").json()["warnings"][0]

    assert warning["entry"] == 2.0  # the breakdown level
    for field in ("stop", "capped_target", "target_3r", "partial_1r", "partial_2r", "trailing_stop",
                  "available_reward_risk", "risk_percent"):
        assert field not in warning


def test_setups_include_pattern_track_record(api_client, db_conn):
    from tests.test_track_record import add_record

    store_setup(db_conn, "HOST")  # high_of_day_break, 1m
    for _ in range(3):
        add_record(db_conn, "target", pattern="high_of_day_break", timeframe="1m")

    setup = api_client.get("/api/setups").json()["setups"][0]

    assert setup["track_record"] == {
        "trades": 3, "win_rate": 1.0, "average_r": 3.0, "average_win_r": 3.0, "tickers": 1, "trading_days": 1,
        "has_enough_history": False,
    }


def test_setups_include_when_they_triggered(api_client, db_conn):
    store_setup(db_conn, "HOST", state="triggered", triggered_at=datetime(2026, 10, 20, 9, 42, tzinfo=EASTERN))
    store_setup(db_conn, "WORX")

    setups = {setup["ticker"]: setup for setup in api_client.get("/api/setups").json()["setups"]}

    assert setups["HOST"]["triggered_at"] == "2026-10-20T09:42:00-04:00"
    assert setups["WORX"]["triggered_at"] is None


def test_setups_include_their_sliding_scale_grade(api_client, db_conn):
    from app.patterns.sliding_scale import Factor, SlidingScale

    grade = SlidingScale(letter="B", points=10, factors=[Factor("Risk/reward", "good", "3.0R (wants 3R+)")])
    store_setup(db_conn, "HOST", sliding_scale=grade)
    store_setup(db_conn, "WORX")

    setups = {setup["ticker"]: setup for setup in api_client.get("/api/setups").json()["setups"]}

    assert setups["HOST"]["sliding_scale"] == {
        "letter": "B", "points": 10,
        "factors": [{"name": "Risk/reward", "grade": "good", "detail": "3.0R (wants 3R+)"}],
    }
    assert setups["WORX"]["sliding_scale"] is None
