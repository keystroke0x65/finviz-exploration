"""Remembers how the most recent full scan went so the Setups view can say so.

Scheduled scans run in the background; when one crashes, the setups on screen quietly
go stale. Only the error's type is kept: messages can contain request URLs, and those
carry the Finviz token.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.market_time import EASTERN
from app.watchlist.feeder import FEEDER_WINDOW_START, is_within_feeder_window

LATEST_SCAN_KEY = "latest_scan"
LAST_COMPLETED_SCAN_KEY = "last_completed_scan_at"
# Two missed 15-minute ticks: one late scan is normal (a long scan, a slow Finviz).
OVERDUE_AFTER_INTERVALS = 2


@dataclass(frozen=True)
class CompletedScan:
    finished_at: datetime
    scanned: int
    failed: list[tuple[str, str]]


@dataclass(frozen=True)
class CrashedScan:
    finished_at: datetime
    error_type: str


ScanAttempt = CompletedScan | CrashedScan


@dataclass(frozen=True)
class ScanStatus:
    latest: ScanAttempt | None
    last_completed_at: datetime | None


def _encode_attempt(attempt: ScanAttempt) -> str:
    if isinstance(attempt, CompletedScan):
        return json.dumps({
            "status": "completed", "finished_at": attempt.finished_at.isoformat(),
            "scanned": attempt.scanned, "failed": attempt.failed,
        })
    return json.dumps({"status": "crashed", "finished_at": attempt.finished_at.isoformat(), "error_type": attempt.error_type})


def _decode_attempt(stored: str) -> ScanAttempt:
    payload = json.loads(stored)
    finished_at = datetime.fromisoformat(payload["finished_at"])
    if payload["status"] == "completed":
        failed = [(ticker, reason) for ticker, reason in payload["failed"]]
        return CompletedScan(finished_at=finished_at, scanned=payload["scanned"], failed=failed)
    return CrashedScan(finished_at=finished_at, error_type=payload["error_type"])


def _write_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _read_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return None if row is None else row["value"]


def save_scan_attempt(conn: sqlite3.Connection, attempt: ScanAttempt) -> None:
    _write_meta(conn, LATEST_SCAN_KEY, _encode_attempt(attempt))
    if isinstance(attempt, CompletedScan):
        _write_meta(conn, LAST_COMPLETED_SCAN_KEY, attempt.finished_at.isoformat())
    conn.commit()


def read_scan_status(conn: sqlite3.Connection) -> ScanStatus:
    latest = _read_meta(conn, LATEST_SCAN_KEY)
    last_completed = _read_meta(conn, LAST_COMPLETED_SCAN_KEY)
    return ScanStatus(
        latest=None if latest is None else _decode_attempt(latest),
        last_completed_at=None if last_completed is None else datetime.fromisoformat(last_completed),
    )


def is_scan_overdue(last_completed_at: datetime | None, now: datetime, interval: timedelta) -> bool:
    """True during scan hours once no full scan has finished for two intervals,
    counting from 4 AM so the morning's first scan has time to run."""
    if not is_within_feeder_window(now):
        return False
    eastern_now = now.astimezone(EASTERN)
    window_opened = datetime.combine(eastern_now.date(), FEEDER_WINDOW_START, tzinfo=EASTERN)
    waiting_since = window_opened if last_completed_at is None else max(last_completed_at, window_opened)
    return now - waiting_since > interval * OVERDUE_AFTER_INTERVALS
