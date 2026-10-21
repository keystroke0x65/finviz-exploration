import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from app.screens.finviz_url import ScreenCriteria

SCREENS_SEEDED_KEY = "screens_seeded"


@dataclass(frozen=True)
class ScreenInput:
    name: str
    criteria: ScreenCriteria
    feeds_watchlist: bool


@dataclass(frozen=True)
class Screen:
    id: int
    name: str
    criteria: ScreenCriteria
    feeds_watchlist: bool
    created_at: datetime
    updated_at: datetime


DEFAULT_SCREENS = [
    ScreenInput(
        name="Top gainers — low float",
        criteria=ScreenCriteria(
            ["geo_usa", "sh_price_u20", "sh_float_u10"], "ta_topgainers", "-change"
        ),
        feeds_watchlist=True,
    ),
    ScreenInput(
        name="After-hours",
        criteria=ScreenCriteria(
            ["geo_usa", "sh_price_u20", "sh_float_u20", "cap_largeunder"], None, None
        ),
        feeds_watchlist=False,
    ),
]


def _to_screen(row: sqlite3.Row) -> Screen:
    return Screen(
        id=row["id"],
        name=row["name"],
        criteria=ScreenCriteria(json.loads(row["filters"]), row["signal"], row["sort_order"]),
        feeds_watchlist=bool(row["feeds_watchlist"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def create_screen(conn: sqlite3.Connection, screen_input: ScreenInput, now: datetime) -> Screen:
    cursor = conn.execute(
        """
        INSERT INTO screens (name, filters, signal, sort_order, feeds_watchlist, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            screen_input.name,
            json.dumps(screen_input.criteria.filters),
            screen_input.criteria.signal,
            screen_input.criteria.order,
            int(screen_input.feeds_watchlist),
            now.isoformat(),
            now.isoformat(),
        ),
    )
    conn.commit()
    return get_screen(conn, cursor.lastrowid)


def get_screen(conn: sqlite3.Connection, screen_id: int) -> Screen | None:
    row = conn.execute("SELECT * FROM screens WHERE id = ?", (screen_id,)).fetchone()
    return None if row is None else _to_screen(row)


def list_screens(conn: sqlite3.Connection) -> list[Screen]:
    return [_to_screen(row) for row in conn.execute("SELECT * FROM screens ORDER BY id")]


def list_feeder_screens(conn: sqlite3.Connection) -> list[Screen]:
    rows = conn.execute("SELECT * FROM screens WHERE feeds_watchlist = 1 ORDER BY id")
    return [_to_screen(row) for row in rows]


def update_screen(
    conn: sqlite3.Connection, screen_id: int, screen_input: ScreenInput, now: datetime
) -> Screen | None:
    cursor = conn.execute(
        """
        UPDATE screens
        SET name = ?, filters = ?, signal = ?, sort_order = ?, feeds_watchlist = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            screen_input.name,
            json.dumps(screen_input.criteria.filters),
            screen_input.criteria.signal,
            screen_input.criteria.order,
            int(screen_input.feeds_watchlist),
            now.isoformat(),
            screen_id,
        ),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return None
    return get_screen(conn, screen_id)


def delete_screen(conn: sqlite3.Connection, screen_id: int) -> bool:
    cursor = conn.execute("DELETE FROM screens WHERE id = ?", (screen_id,))
    conn.commit()
    return cursor.rowcount > 0


def seed_default_screens(conn: sqlite3.Connection, now: datetime) -> None:
    # Tracked by a flag rather than "table is empty" so that a user who
    # deletes every screen doesn't get the defaults back on restart.
    already_seeded = conn.execute(
        "SELECT 1 FROM app_meta WHERE key = ?", (SCREENS_SEEDED_KEY,)
    ).fetchone()
    if already_seeded:
        return
    for screen_input in DEFAULT_SCREENS:
        create_screen(conn, screen_input, now)
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?)", (SCREENS_SEEDED_KEY, now.isoformat())
    )
    conn.commit()
