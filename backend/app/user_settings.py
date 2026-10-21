"""User preferences stored in app_meta."""

import sqlite3

SHOW_SHORT_SETUPS_KEY = "show_short_setups"


def get_show_short_setups(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (SHOW_SHORT_SETUPS_KEY,)).fetchone()
    return row is not None and row["value"] == "true"


def set_show_short_setups(conn: sqlite3.Connection, is_shown: bool) -> None:
    conn.execute(
        """
        INSERT INTO app_meta (key, value) VALUES (?, ?)
        ON CONFLICT (key) DO UPDATE SET value = excluded.value
        """,
        (SHOW_SHORT_SETUPS_KEY, "true" if is_shown else "false"),
    )
    conn.commit()
