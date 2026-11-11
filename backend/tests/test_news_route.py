from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.errors import FinvizRateLimitError
from app.finviz_client import NewsItem
from app.market_time import EASTERN
from app.news_cache import NEWS_CACHE_TTL, read_cached_news, write_cached_news

ITEM = NewsItem(datetime(2026, 11, 10, 7, 0, tzinfo=EASTERN), "GlobeNewswire", "Host wins contract",
                "https://example.com/a")


def test_news_route_returns_items(api_client):
    with patch("app.routes.stocks.get_news", return_value=[ITEM]) as get_news:
        body = api_client.get("/api/stocks/host/news").json()

    get_news.assert_called_once_with("HOST")
    assert body["items"] == [{
        "time": "2026-11-10T07:00:00-05:00", "source": "GlobeNewswire", "title": "Host wins contract",
        "url": "https://example.com/a",
    }]


def test_news_is_cached_until_refreshed(api_client):
    with patch("app.routes.stocks.get_news", return_value=[ITEM]) as get_news:
        api_client.get("/api/stocks/HOST/news")
        api_client.get("/api/stocks/HOST/news")
        api_client.get("/api/stocks/HOST/news?refresh=true")

    assert get_news.call_count == 2


def test_news_route_reports_finviz_rate_limits(api_client):
    with patch("app.routes.stocks.get_news", side_effect=FinvizRateLimitError("news HOST")):
        response = api_client.get("/api/stocks/HOST/news")

    assert response.status_code == 503


def test_cached_news_expires(db_conn):
    fetched = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)
    write_cached_news(db_conn, "HOST", [ITEM], fetched)

    assert read_cached_news(db_conn, "HOST", fetched + NEWS_CACHE_TTL - timedelta(seconds=1)) == [ITEM]
    assert read_cached_news(db_conn, "HOST", fetched + NEWS_CACHE_TTL) is None
