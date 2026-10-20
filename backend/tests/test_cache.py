import json
import sqlite3
import time

import pytest

from app.cache import get_cached_quote, set_cached_quote
from app.config import get_settings


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("QUOTE_CACHE_TTL_MINUTES", "15")
    get_settings.cache_clear()
    return db_path


def test_set_then_get_returns_same_data(temp_db):
    set_cached_quote("AAPL", {"Ticker": "AAPL", "Price": "227.52"})

    result = get_cached_quote("AAPL")

    assert result == {"Ticker": "AAPL", "Price": "227.52"}


def test_get_returns_none_for_uncached_ticker(temp_db):
    result = get_cached_quote("MSFT")

    assert result is None


def test_get_returns_none_for_expired_entry(temp_db):
    set_cached_quote("AAPL", {"Ticker": "AAPL", "Price": "227.52"})
    conn = sqlite3.connect(temp_db)
    stale_time = time.time() - (16 * 60)
    conn.execute(
        "UPDATE quote_cache SET fetched_at = ? WHERE ticker = ?",
        (stale_time, "AAPL"),
    )
    conn.commit()
    conn.close()

    result = get_cached_quote("AAPL")

    assert result is None
