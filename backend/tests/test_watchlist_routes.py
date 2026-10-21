from datetime import datetime, timezone
from unittest.mock import patch

from app.errors import FinvizUnavailableError, TickerNotFoundError
from app.finviz_client import ScreenResult
from app.screens.finviz_url import ScreenCriteria
from app.screens.store import ScreenInput, create_screen

NOW = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)


@patch("app.routes.watchlist.get_quote", return_value={"Ticker": "HOST"})
def test_add_ticker_uppercases_and_validates_with_finviz(mock_get_quote, api_client):
    response = api_client.post("/api/watchlist", json={"ticker": "host"})

    assert response.status_code == 201
    assert response.json()["ticker"] == "HOST"
    assert response.json()["source"] == "manual"
    mock_get_quote.assert_called_once_with("HOST")
    assert [entry["ticker"] for entry in api_client.get("/api/watchlist").json()] == ["HOST"]


@patch("app.routes.watchlist.get_quote", side_effect=TickerNotFoundError("ZZZZ"))
def test_add_unknown_ticker_returns_404(mock_get_quote, api_client):
    response = api_client.post("/api/watchlist", json={"ticker": "ZZZZ"})

    assert response.status_code == 404
    assert "ZZZZ" in response.json()["detail"]
    assert api_client.get("/api/watchlist").json() == []


@patch("app.routes.watchlist.get_quote")
def test_add_rejects_malformed_ticker(mock_get_quote, api_client):
    assert api_client.post("/api/watchlist", json={"ticker": "A" * 20}).status_code == 422
    mock_get_quote.assert_not_called()


@patch("app.routes.watchlist.get_quote", return_value={"Ticker": "HOST"})
def test_remove_entry_then_missing(mock_get_quote, api_client):
    api_client.post("/api/watchlist", json={"ticker": "HOST"})

    assert api_client.delete("/api/watchlist/host").status_code == 204
    assert api_client.delete("/api/watchlist/HOST").status_code == 404


@patch("app.routes.watchlist.get_quote", return_value={"Ticker": "HOST"})
def test_pin_entry_sets_flag(mock_get_quote, api_client):
    api_client.post("/api/watchlist", json={"ticker": "HOST"})

    response = api_client.patch("/api/watchlist/HOST", json={"is_pinned": True})

    assert response.status_code == 200
    assert response.json()["is_pinned"] is True


def test_pin_missing_entry_returns_404(api_client):
    assert api_client.patch("/api/watchlist/NOPE", json={"is_pinned": True}).status_code == 404


def test_refresh_runs_feeder_and_reports_failures(api_client, db_conn):
    create_screen(db_conn, ScreenInput("Good", ScreenCriteria(["geo_usa"], None, None), True), NOW)
    create_screen(db_conn, ScreenInput("Broken", ScreenCriteria(["sh_price_u5"], None, None), True), NOW)

    def fake_run_screen(filters, signal, order):
        if filters == ["sh_price_u5"]:
            raise FinvizUnavailableError("screen", "ReadTimeout")
        return ScreenResult([])

    with patch("app.routes.watchlist.run_screen", side_effect=fake_run_screen):
        response = api_client.post("/api/watchlist/refresh")

    assert response.status_code == 200
    body = response.json()
    assert body["screens_run"] == 2
    assert body["failed_screens"] == [
        {"screen": "Broken", "reason": "Finviz request failed (screen): ReadTimeout"}
    ]


def test_entries_include_expiry_only_for_unpinned_auto_entries(api_client, db_conn, monkeypatch):
    from app.config import get_settings
    from app.watchlist.store import add_manual_entry, record_feeder_hit, set_pinned

    monkeypatch.setenv("WATCHLIST_RETENTION_DAYS", "30")
    get_settings.cache_clear()
    record_feeder_hit(db_conn, "AUTO", 5.0, 1, NOW)
    record_feeder_hit(db_conn, "PINNED", 5.0, 1, NOW)
    set_pinned(db_conn, "PINNED", True)
    add_manual_entry(db_conn, "MANUAL", NOW)

    entries = {entry["ticker"]: entry for entry in api_client.get("/api/watchlist").json()}

    assert entries["AUTO"]["expires_at"] == "2026-11-19T14:00:00Z"
    assert entries["PINNED"]["expires_at"] is None
    assert entries["MANUAL"]["expires_at"] is None


def test_feeder_status_is_null_before_any_run(api_client):
    assert api_client.get("/api/watchlist/feeder-status").json() is None


def test_feeder_status_reports_last_run_failures(api_client, db_conn):
    create_screen(db_conn, ScreenInput("Broken", ScreenCriteria(["sh_price_u5"], None, None), True), NOW)

    with patch(
        "app.routes.watchlist.run_screen",
        side_effect=FinvizUnavailableError("screen", "ReadTimeout"),
    ):
        api_client.post("/api/watchlist/refresh")

    status = api_client.get("/api/watchlist/feeder-status").json()
    assert status["screens_run"] == 1
    assert status["failed_screens"] == [
        {"screen": "Broken", "reason": "Finviz request failed (screen): ReadTimeout"}
    ]
    assert "finished_at" in status


def test_watchlist_entries_include_latest_snapshot(api_client, db_conn):
    from app.scanning.snapshots import save_snapshots
    from app.watchlist.store import add_manual_entry
    from tests.scan_fixtures import snapshot

    add_manual_entry(db_conn, "HOST", NOW)
    add_manual_entry(db_conn, "WORX", NOW)
    save_snapshots(db_conn, [snapshot("HOST", relative_volume=3.2, change=12.5, price=2.83)], NOW)

    entries = {entry["ticker"]: entry for entry in api_client.get("/api/watchlist").json()}

    assert entries["HOST"]["snapshot"] == {
        "price": 2.83, "change_percent": 12.5, "after_hours_change_percent": 0.0,
        "relative_volume": 3.2, "fetched_at": "2026-10-20T14:00:00Z",
    }
    assert entries["WORX"]["snapshot"] is None


def test_watchlist_entries_include_verdict(api_client, db_conn):
    from app.patterns.verdict import Verdict
    from app.scanning.verdicts import save_verdict
    from app.watchlist.store import add_manual_entry

    add_manual_entry(db_conn, "HOST", NOW)
    save_verdict(db_conn, "HOST", Verdict("leans_short", -0.3, {}, ["Volume heavier on down bars"]), NOW)

    entry = api_client.get("/api/watchlist").json()[0]

    assert entry["verdict"]["call"] == "leans_short"
