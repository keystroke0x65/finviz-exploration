"""Latest price/change per watchlist ticker, saved by each scan for the watchlist view."""

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime

from app.finviz_client import ScreenRow


def save_snapshots(conn: sqlite3.Connection, rows: list[ScreenRow], now: datetime) -> None:
    conn.executemany(
        """
        INSERT INTO ticker_snapshots (ticker, data, fetched_at) VALUES (?, ?, ?)
        ON CONFLICT (ticker) DO UPDATE SET data = excluded.data, fetched_at = excluded.fetched_at
        """,
        [(row.ticker, json.dumps(asdict(row)), now.isoformat()) for row in rows],
    )
    conn.commit()


def read_snapshots(conn: sqlite3.Connection) -> dict[str, tuple[ScreenRow, datetime]]:
    rows = conn.execute("SELECT ticker, data, fetched_at FROM ticker_snapshots")
    return {
        row["ticker"]: (ScreenRow(**json.loads(row["data"])), datetime.fromisoformat(row["fetched_at"]))
        for row in rows
    }
