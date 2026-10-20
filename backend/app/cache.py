import json
import sqlite3
import time

from app.config import get_settings


def _connect() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_cache (
            ticker TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            fetched_at REAL NOT NULL
        )
        """
    )
    return conn


def get_cached_quote(ticker: str) -> dict | None:
    settings = get_settings()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT data, fetched_at FROM quote_cache WHERE ticker = ?",
            (ticker,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    data, fetched_at = row
    ttl_seconds = settings.quote_cache_ttl_minutes * 60
    if time.time() - fetched_at > ttl_seconds:
        return None

    return json.loads(data)


def set_cached_quote(ticker: str, data: dict) -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO quote_cache (ticker, data, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET data = excluded.data, fetched_at = excluded.fetched_at
            """,
            (ticker, json.dumps(data), time.time()),
        )
        conn.commit()
    finally:
        conn.close()
