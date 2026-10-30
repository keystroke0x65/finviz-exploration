"""How hot the market is: the count of US stocks up 30%+ (the sliding scale's
'environment of the market' factor), counted once per full scan."""

import json
import sqlite3
from datetime import datetime

from app.finviz_client import ScreenRow
from app.market_time import EASTERN
from app.patterns.sliding_scale import REGULAR_OPEN, MarketGainers

# Finviz's change filter stops at "Up 20%" and silently ignores an "Up 30%"
# code, so the scan fetches 20%+ movers and counts the 30%+ ones itself.
MARKET_MOVERS_FILTERS = ["geo_usa", "ta_change_u20"]
BIG_GAINER_PERCENT = 30.0
MARKET_GAINERS_KEY = "market_gainers"


def count_big_gainers(rows: list[ScreenRow]) -> int:
    return sum(1 for row in rows if row.change_percent is not None and row.change_percent >= BIG_GAINER_PERCENT)


def save_market_gainers(conn: sqlite3.Connection, count: int, counted_at: datetime) -> None:
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (MARKET_GAINERS_KEY, json.dumps({"count": count, "counted_at": counted_at.isoformat()})),
    )
    conn.commit()


def read_market_gainers(conn: sqlite3.Connection, now: datetime) -> MarketGainers | None:
    """Today's latest count, or None if none was made today."""
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (MARKET_GAINERS_KEY,)).fetchone()
    if row is None:
        return None
    payload = json.loads(row["value"])
    counted_at = datetime.fromisoformat(payload["counted_at"]).astimezone(EASTERN)
    if counted_at.date() != now.astimezone(EASTERN).date():
        return None
    # Before the open, Finviz's change column still shows the previous session.
    return MarketGainers(count=payload["count"], is_previous_session=counted_at.time() < REGULAR_OPEN)
