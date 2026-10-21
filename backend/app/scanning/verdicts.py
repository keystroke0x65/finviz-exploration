"""Each scanned stock's latest verdict, for the Setups, Watchlist and Stock views."""

import json
import sqlite3
from datetime import datetime

from app.patterns.verdict import Verdict


def save_verdict(conn: sqlite3.Connection, ticker: str, verdict: Verdict, now: datetime) -> None:
    conn.execute(
        """
        INSERT INTO ticker_verdicts (ticker, call, score, parts, reasons, computed_at) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (ticker) DO UPDATE SET call = excluded.call, score = excluded.score, parts = excluded.parts,
            reasons = excluded.reasons, computed_at = excluded.computed_at
        """,
        (ticker, verdict.call, verdict.score, json.dumps(verdict.parts), json.dumps(verdict.reasons), now.isoformat()),
    )
    conn.commit()


def read_verdicts(conn: sqlite3.Connection) -> dict[str, tuple[Verdict, datetime]]:
    return {
        row["ticker"]: (
            Verdict(row["call"], row["score"], json.loads(row["parts"]), json.loads(row["reasons"])),
            datetime.fromisoformat(row["computed_at"]),
        )
        for row in conn.execute("SELECT * FROM ticker_verdicts")
    }
