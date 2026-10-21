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
        return ScreenResult([], False)

    with patch("app.routes.watchlist.run_screen", side_effect=fake_run_screen):
        response = api_client.post("/api/watchlist/refresh")

    assert response.status_code == 200
    body = response.json()
    assert body["screens_run"] == 2
    assert body["failed_screens"] == [
        {"screen": "Broken", "reason": "Finviz request failed (screen): ReadTimeout"}
    ]
