import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

# US market sessions (pre-market, regular, after-hours) are defined in New
# York time, so a "day" a stock ran is an Eastern calendar day: a hit at
# 22:30 ET belongs to that day's after-hours, not to tomorrow in UTC.
EASTERN = ZoneInfo("America/New_York")

EntrySource = Literal["auto", "manual"]


@dataclass(frozen=True)
class Appearance:
    seen_on: date
    change_percent: float | None
    screen_id: int


@dataclass(frozen=True)
class WatchlistEntry:
    ticker: str
    source: EntrySource
    added_at: datetime
    last_seen_in_feeder_at: datetime | None
    is_pinned: bool
    appearances: list[Appearance]


def _to_stored_time(moment: datetime) -> str:
    # Always UTC with the same offset format, so stored times compare
    # correctly as strings in SQL.
    return moment.astimezone(timezone.utc).isoformat()


def _from_stored_time(stored: str | None) -> datetime | None:
    return None if stored is None else datetime.fromisoformat(stored)


def _eastern_date(moment: datetime) -> date:
    return moment.astimezone(EASTERN).date()


def _load_appearances(conn: sqlite3.Connection, ticker: str) -> list[Appearance]:
    rows = conn.execute(
        """
        SELECT seen_on, change_percent, screen_id FROM watchlist_appearances
        WHERE ticker = ? ORDER BY seen_on DESC, screen_id
        """,
        (ticker,),
    )
    return [
        Appearance(date.fromisoformat(row["seen_on"]), row["change_percent"], row["screen_id"])
        for row in rows
    ]


def _to_entry(conn: sqlite3.Connection, row: sqlite3.Row) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=row["ticker"],
        source=row["source"],
        added_at=_from_stored_time(row["added_at"]),
        last_seen_in_feeder_at=_from_stored_time(row["last_seen_in_feeder_at"]),
        is_pinned=bool(row["is_pinned"]),
        appearances=_load_appearances(conn, row["ticker"]),
    )


def get_entry(conn: sqlite3.Connection, ticker: str) -> WatchlistEntry | None:
    row = conn.execute("SELECT * FROM watchlist_entries WHERE ticker = ?", (ticker,)).fetchone()
    return None if row is None else _to_entry(conn, row)


def list_entries(conn: sqlite3.Connection) -> list[WatchlistEntry]:
    rows = conn.execute(
        """
        SELECT * FROM watchlist_entries
        ORDER BY last_seen_in_feeder_at IS NULL, last_seen_in_feeder_at DESC, ticker
        """
    )
    return [_to_entry(conn, row) for row in rows.fetchall()]


def record_feeder_hit(
    conn: sqlite3.Connection,
    ticker: str,
    change_percent: float | None,
    screen_id: int,
    now: datetime,
) -> Literal["added", "updated"]:
    stored_now = _to_stored_time(now)
    cursor = conn.execute(
        "UPDATE watchlist_entries SET last_seen_in_feeder_at = ? WHERE ticker = ?",
        (stored_now, ticker),
    )
    outcome: Literal["added", "updated"] = "updated" if cursor.rowcount else "added"
    if outcome == "added":
        conn.execute(
            """
            INSERT INTO watchlist_entries (ticker, source, added_at, last_seen_in_feeder_at)
            VALUES (?, 'auto', ?, ?)
            """,
            (ticker, stored_now, stored_now),
        )
    conn.execute(
        """
        INSERT INTO watchlist_appearances (ticker, seen_on, change_percent, screen_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (ticker, seen_on, screen_id) DO UPDATE SET change_percent = excluded.change_percent
        """,
        (ticker, _eastern_date(now).isoformat(), change_percent, screen_id),
    )
    conn.commit()
    return outcome


def add_manual_entry(conn: sqlite3.Connection, ticker: str, now: datetime) -> WatchlistEntry:
    conn.execute(
        """
        INSERT INTO watchlist_entries (ticker, source, added_at) VALUES (?, 'manual', ?)
        ON CONFLICT (ticker) DO UPDATE SET source = 'manual'
        """,
        (ticker, _to_stored_time(now)),
    )
    conn.commit()
    return get_entry(conn, ticker)


def remove_entry(conn: sqlite3.Connection, ticker: str) -> bool:
    cursor = conn.execute("DELETE FROM watchlist_entries WHERE ticker = ?", (ticker,))
    conn.commit()
    return cursor.rowcount > 0


def set_pinned(conn: sqlite3.Connection, ticker: str, is_pinned: bool) -> WatchlistEntry | None:
    cursor = conn.execute(
        "UPDATE watchlist_entries SET is_pinned = ? WHERE ticker = ?", (int(is_pinned), ticker)
    )
    conn.commit()
    if cursor.rowcount == 0:
        return None
    return get_entry(conn, ticker)


def expire_stale_entries(
    conn: sqlite3.Connection, now: datetime, retention_days: int
) -> list[str]:
    cutoff = _to_stored_time(now - timedelta(days=retention_days))
    rows = conn.execute(
        """
        DELETE FROM watchlist_entries
        WHERE source = 'auto' AND is_pinned = 0 AND last_seen_in_feeder_at < ?
        RETURNING ticker
        """,
        (cutoff,),
    ).fetchall()
    conn.commit()
    return sorted(row["ticker"] for row in rows)


def entry_expires_at(entry: WatchlistEntry, retention_days: int) -> datetime | None:
    """When `expire_stale_entries` will drop this entry, or None if it never will."""
    if entry.source == "manual" or entry.is_pinned or entry.last_seen_in_feeder_at is None:
        return None
    return entry.last_seen_in_feeder_at + timedelta(days=retention_days)
