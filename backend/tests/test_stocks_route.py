from unittest.mock import patch

from fastapi.testclient import TestClient

from app.errors import FinvizAuthError, TickerNotFoundError
from app.main import app

client = TestClient(app)

QUOTE_DATA = {"Ticker": "AAPL", "Company": "Apple Inc.", "Price": "227.52"}


@patch("app.routes.stocks.get_cached_quote", return_value=None)
@patch("app.routes.stocks.set_cached_quote")
@patch("app.routes.stocks.get_quote", return_value=QUOTE_DATA)
def test_get_stock_returns_quote_on_cache_miss(mock_get_quote, mock_set, mock_get_cached):
    response = client.get("/api/stocks/AAPL")

    assert response.status_code == 200
    assert response.json()["Ticker"] == "AAPL"
    mock_get_quote.assert_called_once_with("AAPL")
    mock_set.assert_called_once_with("AAPL", QUOTE_DATA)


@patch("app.routes.stocks.get_cached_quote", return_value=QUOTE_DATA)
@patch("app.routes.stocks.get_quote")
def test_get_stock_uses_cache_on_hit(mock_get_quote, mock_get_cached):
    response = client.get("/api/stocks/AAPL")

    assert response.status_code == 200
    assert response.json()["Ticker"] == "AAPL"
    mock_get_quote.assert_not_called()


@patch("app.routes.stocks.get_cached_quote", return_value=None)
@patch("app.routes.stocks.get_quote", side_effect=TickerNotFoundError("ZZZZ"))
def test_get_stock_returns_404_for_unknown_ticker(mock_get_quote, mock_get_cached):
    response = client.get("/api/stocks/ZZZZ")

    assert response.status_code == 404
    assert "ZZZZ" in response.json()["detail"]


@patch("app.routes.stocks.get_cached_quote", return_value=None)
@patch("app.routes.stocks.get_quote", side_effect=FinvizAuthError())
def test_get_stock_returns_502_on_auth_failure(mock_get_quote, mock_get_cached):
    response = client.get("/api/stocks/AAPL")

    assert response.status_code == 502
    assert "auth token" in response.json()["detail"]


@patch("app.routes.stocks.set_cached_quote")
@patch("app.routes.stocks.get_cached_quote", return_value=QUOTE_DATA)
@patch("app.routes.stocks.get_quote", return_value=QUOTE_DATA)
def test_refresh_bypasses_cache(mock_get_quote, mock_get_cached, mock_set):
    response = client.get("/api/stocks/AAPL/refresh")

    assert response.status_code == 200
    mock_get_quote.assert_called_once_with("AAPL")
