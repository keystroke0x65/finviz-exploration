from datetime import datetime

import pytest
import responses
from responses import matchers

from app.config import get_settings
from app.errors import FinvizUnavailableError
from app.finviz_client import (
    FINVIZ_BARS_URL,
    SCREEN_COLUMN_IDS,
    Bar,
    get_bars,
    get_snapshots,
    parse_bar_time,
)
from app.market_time import EASTERN

FINVIZ_EXPORT_URL = "https://elite.finviz.com/export/screener"
TOKEN = "test-token"
BARS_HEADER = "Date,Open,High,Low,Close,Volume\n"
SNAPSHOT_HEADER = (
    "Ticker,Company,Country,Market Cap,Shares Float,Average Volume,Relative Volume,Price,"
    "Change,Volume,After-Hours Close,After-Hours Change,News Time,News URL,News Title\n"
)


@pytest.fixture(autouse=True)
def finviz_token(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_parse_intraday_timestamp_after_hours():
    # Finviz writes a 24-hour clock with a redundant AM/PM suffix.
    assert parse_bar_time("10/20/2026 19:59 PM", "1m") == datetime(2026, 10, 20, 19, 59, tzinfo=EASTERN)


def test_parse_intraday_timestamp_morning():
    assert parse_bar_time("10/06/2026 04:00 AM", "5m") == datetime(2026, 10, 6, 4, 0, tzinfo=EASTERN)


def test_parse_daily_date():
    assert parse_bar_time("10/20/2026", "daily") == datetime(2026, 10, 20, 0, 0, tzinfo=EASTERN)


@responses.activate
def test_get_bars_parses_rows_oldest_first():
    responses.add(
        responses.GET,
        FINVIZ_BARS_URL,
        body=BARS_HEADER
        + "10/20/2026 19:58 PM,338.068,338.08,337.99,338,2819\n"
        + "10/20/2026 19:59 PM,338.0,338.1,337.9,338.05,1500\n",
    )

    bars = get_bars("AAPL", "1m")

    assert bars == [
        Bar(datetime(2026, 10, 20, 19, 58, tzinfo=EASTERN), 338.068, 338.08, 337.99, 338.0, 2819),
        Bar(datetime(2026, 10, 20, 19, 59, tzinfo=EASTERN), 338.0, 338.1, 337.9, 338.05, 1500),
    ]


@responses.activate
def test_get_bars_sends_period_code():
    responses.add(
        responses.GET,
        FINVIZ_BARS_URL,
        body=BARS_HEADER,
        match=[matchers.query_param_matcher({"t": "HOST", "p": "i5", "auth": TOKEN})],
    )

    assert get_bars("HOST", "5m") == []


@responses.activate
def test_get_bars_returns_empty_for_header_only_csv():
    responses.add(responses.GET, FINVIZ_BARS_URL, body=BARS_HEADER)

    assert get_bars("HOST", "daily") == []


@responses.activate
def test_get_bars_raises_unavailable_on_html_page():
    responses.add(responses.GET, FINVIZ_BARS_URL, body="<html><body>Login</body></html>")

    with pytest.raises(FinvizUnavailableError, match="unexpected response format"):
        get_bars("HOST", "1m")


@responses.activate
def test_get_bars_raises_unavailable_on_non_numeric_cell():
    responses.add(responses.GET, FINVIZ_BARS_URL, body=BARS_HEADER + "10/20/2026,1,2,x,1.5,10\n")

    with pytest.raises(FinvizUnavailableError, match="unexpected response format"):
        get_bars("HOST", "daily")


@responses.activate
def test_get_snapshots_batches_tickers():
    tickers = [f"T{index:03d}" for index in range(150)]
    for batch in (tickers[:100], tickers[100:]):
        responses.add(
            responses.GET,
            FINVIZ_EXPORT_URL,
            body=SNAPSHOT_HEADER + f"{batch[0]},Co,USA,1,1,1,2.5,3.0,5%,100,3.1,1%,,,\n",
            match=[
                matchers.query_param_matcher(
                    {"v": "152", "c": SCREEN_COLUMN_IDS, "t": ",".join(batch), "auth": TOKEN}
                )
            ],
        )

    rows = get_snapshots(tickers)

    assert [row.ticker for row in rows] == ["T000", "T100"]
    assert rows[0].relative_volume == 2.5


def test_get_snapshots_makes_no_request_for_empty_list():
    # No responses registered and not activated: a real request would fail loudly.
    assert get_snapshots([]) == []


@responses.activate
def test_get_bars_raises_unavailable_on_empty_cell():
    responses.add(responses.GET, FINVIZ_BARS_URL, body=BARS_HEADER + "10/20/2026,1,2,,1.5,10\n")

    with pytest.raises(FinvizUnavailableError, match="unexpected response format"):
        get_bars("HOST", "daily")


@responses.activate
def test_get_bars_raises_unavailable_when_a_column_is_missing():
    responses.add(responses.GET, FINVIZ_BARS_URL, body="Date,High,Low,Close,Volume\n10/20/2026,2,1,1.5,10\n")

    with pytest.raises(FinvizUnavailableError, match="unexpected response format"):
        get_bars("HOST", "daily")


@responses.activate
def test_get_bars_drops_bars_with_non_positive_prices():
    responses.add(
        responses.GET,
        FINVIZ_BARS_URL,
        body=BARS_HEADER + "10/19/2026,1,2,0,1.5,10\n10/20/2026,1.5,2,1.4,1.8,10\n",
    )

    assert [bar.close for bar in get_bars("HOST", "daily")] == [1.8]
