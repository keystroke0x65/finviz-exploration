"""Remembers the outcome of the most recent feeder run so the UI can show it.

The feeder mostly runs in the background, where nobody sees its errors; an
expired token or rate limiting would otherwise stop the watchlist growing
with no visible reason.
"""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime

LAST_FEEDER_RUN_KEY = "last_feeder_run"


@dataclass(frozen=True)
class FeederResult:
    screens_run: int
    tickers_added: list[str]
    tickers_updated: list[str]
    tickers_expired: list[str]
    failed_screens: list[tuple[str, str]]


@dataclass(frozen=True)
class LastFeederRun:
    finished_at: datetime
    result: FeederResult


def save_last_feeder_run(conn: sqlite3.Connection, finished_at: datetime, result: FeederResult) -> None:
    payload = json.dumps({"finished_at": finished_at.isoformat(), "result": asdict(result)})
    conn.execute(
        """
        INSERT INTO app_meta (key, value) VALUES (?, ?)
        ON CONFLICT (key) DO UPDATE SET value = excluded.value
        """,
        (LAST_FEEDER_RUN_KEY, payload),
    )
    conn.commit()


def get_last_feeder_run(conn: sqlite3.Connection) -> LastFeederRun | None:
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (LAST_FEEDER_RUN_KEY,)).fetchone()
    if row is None:
        return None
    payload = json.loads(row["value"])
    stored_result = payload["result"]
    result = FeederResult(
        **{**stored_result, "failed_screens": [tuple(item) for item in stored_result["failed_screens"]]}
    )
    return LastFeederRun(finished_at=datetime.fromisoformat(payload["finished_at"]), result=result)
