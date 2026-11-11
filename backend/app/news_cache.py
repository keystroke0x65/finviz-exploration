"""Short-lived copy of each stock's Finviz news, so revisiting a stock costs no request."""

import json
import sqlite3
from datetime import datetime, timedelta

from app.finviz_client import NewsItem

# News changes slowly next to prices; "Scan this stock" refreshes it anyway.
NEWS_CACHE_TTL = timedelta(minutes=10)


def write_cached_news(conn: sqlite3.Connection, ticker: str, items: list[NewsItem], now: datetime) -> None:
    payload = json.dumps([[item.time.isoformat(), item.source, item.title, item.url] for item in items])
    conn.execute(
        """
        INSERT INTO news_cache (ticker, fetched_at, items) VALUES (?, ?, ?)
        ON CONFLICT (ticker) DO UPDATE SET fetched_at = excluded.fetched_at, items = excluded.items
        """,
        (ticker, now.isoformat(), payload),
    )
    conn.commit()


def read_cached_news(conn: sqlite3.Connection, ticker: str, now: datetime) -> list[NewsItem] | None:
    """The cached items, or None when there are none or they're older than NEWS_CACHE_TTL."""
    row = conn.execute("SELECT fetched_at, items FROM news_cache WHERE ticker = ?", (ticker,)).fetchone()
    if row is None or now - datetime.fromisoformat(row["fetched_at"]) >= NEWS_CACHE_TTL:
        return None
    return [NewsItem(datetime.fromisoformat(moment), source, title, url) for moment, source, title, url in json.loads(row["items"])]
