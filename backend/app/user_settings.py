"""User preferences stored in app_meta."""

import json
import sqlite3

SHOW_SHORT_SETUPS_KEY = "show_short_setups"
SCREEN_COLUMN_WIDTHS_KEY = "screen_column_widths"
JOURNAL_SETTINGS_KEY = "journal_settings"
JOURNAL_SETTING_NAMES = ("risk_per_trade", "max_position", "max_daily_loss")


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


def get_screen_column_widths(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (SCREEN_COLUMN_WIDTHS_KEY,)).fetchone()
    return {} if row is None else json.loads(row["value"])


def set_screen_column_widths(conn: sqlite3.Connection, widths: dict[str, int]) -> None:
    conn.execute(
        """
        INSERT INTO app_meta (key, value) VALUES (?, ?)
        ON CONFLICT (key) DO UPDATE SET value = excluded.value
        """,
        (SCREEN_COLUMN_WIDTHS_KEY, json.dumps(widths)),
    )
    conn.commit()


def get_journal_settings(conn: sqlite3.Connection) -> dict[str, float | None]:
    """Risk per trade, max position and max daily loss in dollars; None when not set."""
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (JOURNAL_SETTINGS_KEY,)).fetchone()
    stored = {} if row is None else json.loads(row["value"])
    return {name: stored.get(name) for name in JOURNAL_SETTING_NAMES}


def set_journal_settings(conn: sqlite3.Connection, settings: dict[str, float | None]) -> None:
    conn.execute(
        """
        INSERT INTO app_meta (key, value) VALUES (?, ?)
        ON CONFLICT (key) DO UPDATE SET value = excluded.value
        """,
        (JOURNAL_SETTINGS_KEY, json.dumps({name: settings.get(name) for name in JOURNAL_SETTING_NAMES})),
    )
    conn.commit()
