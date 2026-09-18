import pytest
import responses

from app.config import get_settings
from app.errors import FinvizAuthError, TickerNotFoundError
from app.finviz_client import get_quote


def test_get_settings_reads_env(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token-123")
    monkeypatch.setenv("QUOTE_CACHE_TTL_MINUTES", "30")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.finviz_api_token == "test-token-123"
    assert settings.quote_cache_ttl_minutes == 30


FINVIZ_EXPORT_URL = "https://elite.finviz.com/export.ashx"

VALID_QUOTE_CSV = (
    "Ticker,Company,Sector,Price,Change,Volume,Market Cap,P/E\n"
    "AAPL,Apple Inc.,Technology,227.52,1.35%,48291012,3.45T,34.2\n"
)

EMPTY_CSV = "Ticker,Company,Sector,Price,Change,Volume,Market Cap,P/E\n"


@responses.activate
def test_get_quote_returns_parsed_fields(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    get_settings.cache_clear()
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body=VALID_QUOTE_CSV,
        status=200,
    )

    result = get_quote("AAPL")

    assert result["Ticker"] == "AAPL"
    assert result["Price"] == "227.52"
    assert result["Sector"] == "Technology"


@responses.activate
def test_get_quote_raises_not_found_for_empty_csv(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    get_settings.cache_clear()
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body=EMPTY_CSV,
        status=200,
    )

    with pytest.raises(TickerNotFoundError, match="ZZZZINVALID"):
        get_quote("ZZZZINVALID")


@responses.activate
def test_get_quote_raises_auth_error_on_401(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "bad-token")
    get_settings.cache_clear()
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body="Invalid auth token",
        status=401,
    )

    with pytest.raises(FinvizAuthError):
        get_quote("AAPL")


# Finviz omits some columns for certain tickers (e.g. no P/E for an
# unprofitable company), which pandas reads as a blank cell -> float NaN.
QUOTE_CSV_WITH_MISSING_FIELD = (
    "Ticker,Company,Sector,Price,Change,Volume,Market Cap,P/E\n"
    "AAPL,Apple Inc.,Technology,227.52,1.35%,48291012,3.45T,\n"
)


@responses.activate
def test_get_quote_converts_missing_fields_to_none_not_nan(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    get_settings.cache_clear()
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body=QUOTE_CSV_WITH_MISSING_FIELD,
        status=200,
    )

    result = get_quote("AAPL")

    assert result["P/E"] is None
