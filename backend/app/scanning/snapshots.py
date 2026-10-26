"""Latest price/change per watchlist ticker, saved by each scan for the watchlist view."""

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime

from app.finviz_client import ScreenRow
from app.market_time import EASTERN


def _encode_row(row: ScreenRow) -> str:
    return json.dumps({**asdict(row), "news_time": row.news_time.isoformat() if row.news_time else None})


def _decode_news_time(stored: str | None) -> datetime | None:
    if stored is None:
        return None
    news_time = datetime.fromisoformat(stored)
    # Rows saved before 2026-10-26 hold Finviz's raw text, which has no zone but is Eastern.
    return news_time if news_time.tzinfo else news_time.replace(tzinfo=EASTERN)


def _decode_row(data: str) -> ScreenRow:
    fields = json.loads(data)
    return ScreenRow(**{**fields, "news_time": _decode_news_time(fields["news_time"])})


def save_snapshots(conn: sqlite3.Connection, rows: list[ScreenRow], now: datetime) -> None:
    conn.executemany(
        """
        INSERT INTO ticker_snapshots (ticker, data, fetched_at) VALUES (?, ?, ?)
        ON CONFLICT (ticker) DO UPDATE SET data = excluded.data, fetched_at = excluded.fetched_at
        """,
        [(row.ticker, _encode_row(row), now.isoformat()) for row in rows],
    )
    conn.commit()


def read_snapshots(conn: sqlite3.Connection) -> dict[str, tuple[ScreenRow, datetime]]:
    rows = conn.execute("SELECT ticker, data, fetched_at FROM ticker_snapshots")
    return {
        row["ticker"]: (_decode_row(row["data"]), datetime.fromisoformat(row["fetched_at"]))
        for row in rows
    }
