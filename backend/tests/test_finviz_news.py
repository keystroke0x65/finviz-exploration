from datetime import datetime

import pytest
import responses

from app.config import get_settings
from app.errors import FinvizRateLimitError
from app.finviz_client import FINVIZ_NEWS_URL, NewsItem, get_news
from app.market_time import EASTERN

NEWS_CSV = (
    "Title,Source,Date,Url,Category,Ticker\n"
    'Energous Shares Rise 1.4%,InvestorsHub,2026-09-15 06:37:47,https://elite.finviz.com/news/1/a,Stock,WATT\n'
    '"Energous Reports Q2 Results, Revenue Up",GlobeNewswire,2026-08-12 16:15:00,https://example.com/q2,Stock,WATT\n'
    "Bad date row,Somewhere,not a date,https://example.com/x,Stock,WATT\n"
    "Script link,Somewhere,2026-08-01 09:00:00,javascript:alert(1),Stock,WATT\n"
)


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@responses.activate
def test_get_news_parses_items_newest_first_in_eastern_time():
    responses.add(responses.GET, FINVIZ_NEWS_URL, body=NEWS_CSV, status=200)

    items = get_news("WATT")

    assert items == [
        NewsItem(datetime(2026, 9, 15, 6, 37, 47, tzinfo=EASTERN), "InvestorsHub", "Energous Shares Rise 1.4%",
                 "https://elite.finviz.com/news/1/a"),
        NewsItem(datetime(2026, 8, 12, 16, 15, tzinfo=EASTERN), "GlobeNewswire", "Energous Reports Q2 Results, Revenue Up",
                 "https://example.com/q2"),
    ]
    assert responses.calls[0].request.params == {"v": "3", "t": "WATT", "auth": "test-token"}


@responses.activate
def test_get_news_of_a_quiet_stock_is_empty():
    responses.add(responses.GET, FINVIZ_NEWS_URL, body="Title,Source,Date,Url,Category,Ticker\n", status=200)

    assert get_news("WATT") == []


@responses.activate
def test_get_news_passes_on_rate_limits():
    responses.add(responses.GET, FINVIZ_NEWS_URL, status=429)

    with pytest.raises(FinvizRateLimitError):
        get_news("WATT")
