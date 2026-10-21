import pytest
import requests
import responses
from responses import matchers

from app import finviz_client
from app.config import get_settings
from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import (
    SCREEN_COLUMN_IDS,
    UNFILTERED_ROW_THRESHOLD,
    ScreenRow,
    run_screen,
)

FINVIZ_EXPORT_URL = "https://elite.finviz.com/export/screener"
TOKEN = "test-token"

SCREEN_HEADER = (
    "Ticker,Company,Country,Market Cap,Shares Float,Average Volume,Relative Volume,Price,"
    "Change,Volume,After-Hours Close,After-Hours Change,News Time,News URL,News Title\n"
)
SCREEN_CSV = (
    SCREEN_HEADER
    + "HOST,Host Digital Inc,USA,79.80,5.46,433.04,14.22,2.83,47.40%,6158186,2.73,-3.53%,"
    "2026-10-20 10:36:03,https://elite.finviz.com/news/1,Buyback\n"
    "NOAH,Noah Co,USA,12.00,,,,1.10,,,,,,,\n"
)


@pytest.fixture(autouse=True)
def finviz_token(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _csv_with_rows(row_count: int) -> str:
    row = "AAA,A Co,USA,1,1,1,1,1,1%,1,1,1%,,,\n"
    return SCREEN_HEADER + row * row_count


@responses.activate
def test_run_screen_parses_typed_rows():
    responses.add(responses.GET, FINVIZ_EXPORT_URL, body=SCREEN_CSV, status=200)

    result = run_screen(["geo_usa"], None, None)

    assert result.rows[0] == ScreenRow(
        ticker="HOST",
        company="Host Digital Inc",
        country="USA",
        market_cap_millions=79.80,
        float_millions=5.46,
        average_volume_thousands=433.04,
        relative_volume=14.22,
        price=2.83,
        change_percent=47.40,
        volume=6158186,
        after_hours_close=2.73,
        after_hours_change_percent=-3.53,
        news_time="2026-10-20 10:36:03",
        news_url="https://elite.finviz.com/news/1",
        news_title="Buyback",
    )
    assert result.rows[1].ticker == "NOAH"
    assert result.rows[1].float_millions is None
    assert result.rows[1].change_percent is None
    assert result.rows[1].volume is None
    assert result.is_possibly_unfiltered is False


@responses.activate
def test_run_screen_sends_codes_and_columns():
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body=SCREEN_HEADER,
        status=200,
        match=[
            matchers.query_param_matcher(
                {
                    "v": "152",
                    "c": SCREEN_COLUMN_IDS,
                    "f": "geo_usa,sh_price_u20",
                    "s": "ta_topgainers",
                    "o": "-change",
                    "auth": TOKEN,
                }
            )
        ],
    )

    run_screen(["geo_usa", "sh_price_u20"], "ta_topgainers", "-change")

    assert len(responses.calls) == 1


@responses.activate
def test_run_screen_omits_signal_and_order_when_none():
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body=SCREEN_HEADER,
        status=200,
        match=[
            matchers.query_param_matcher(
                {"v": "152", "c": SCREEN_COLUMN_IDS, "f": "geo_usa", "auth": TOKEN}
            )
        ],
    )

    run_screen(["geo_usa"], None, None)

    assert len(responses.calls) == 1


@responses.activate
def test_run_screen_returns_empty_rows_for_header_only_csv():
    responses.add(responses.GET, FINVIZ_EXPORT_URL, body=SCREEN_HEADER, status=200)

    result = run_screen(["geo_usa"], None, None)

    assert result.rows == []
    assert result.is_possibly_unfiltered is False


@responses.activate
def test_run_screen_flags_result_over_threshold():
    responses.add(
        responses.GET, FINVIZ_EXPORT_URL, body=_csv_with_rows(UNFILTERED_ROW_THRESHOLD + 1)
    )
    responses.add(responses.GET, FINVIZ_EXPORT_URL, body=_csv_with_rows(UNFILTERED_ROW_THRESHOLD))

    over_threshold = run_screen(["geo_usa"], None, None)
    at_threshold = run_screen(["geo_usa"], None, None)

    assert over_threshold.is_possibly_unfiltered is True
    assert at_threshold.is_possibly_unfiltered is False


@responses.activate
def test_run_screen_raises_auth_error_on_401():
    responses.add(responses.GET, FINVIZ_EXPORT_URL, status=401)

    with pytest.raises(FinvizAuthError):
        run_screen(["geo_usa"], None, None)


@responses.activate
def test_run_screen_raises_rate_limit_error_on_429():
    responses.add(responses.GET, FINVIZ_EXPORT_URL, status=429)

    with pytest.raises(FinvizRateLimitError):
        run_screen(["geo_usa"], None, None)


@responses.activate
def test_run_screen_raises_unavailable_on_timeout():
    responses.add(responses.GET, FINVIZ_EXPORT_URL, body=requests.Timeout("timed out"))

    with pytest.raises(FinvizUnavailableError):
        run_screen(["geo_usa"], None, None)


@responses.activate
def test_run_screen_raises_unavailable_on_server_error():
    responses.add(responses.GET, FINVIZ_EXPORT_URL, status=503)

    with pytest.raises(FinvizUnavailableError):
        run_screen(["geo_usa"], None, None)


@responses.activate
def test_run_screen_error_messages_never_contain_token():
    responses.add(responses.GET, FINVIZ_EXPORT_URL, status=401)
    responses.add(responses.GET, FINVIZ_EXPORT_URL, status=429)
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body=requests.ConnectionError(f"failed for {FINVIZ_EXPORT_URL}?auth={TOKEN}"),
    )
    responses.add(responses.GET, FINVIZ_EXPORT_URL, status=500)

    messages = []
    for _ in range(4):
        with pytest.raises(Exception) as exc_info:
            run_screen(["geo_usa"], None, None)
        messages.append(str(exc_info.value))

    assert all(TOKEN not in message for message in messages)


def test_requests_are_paced():
    sleeps: list[float] = []
    clock_times = iter([100.0, 100.2])
    pacer = finviz_client._RequestPacer(
        min_interval_seconds=1.0, clock=lambda: next(clock_times), sleep=sleeps.append
    )

    pacer.wait_for_turn()
    pacer.wait_for_turn()

    assert sleeps == [pytest.approx(0.8)]
