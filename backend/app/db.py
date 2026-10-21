import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS screens (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    filters TEXT NOT NULL,
    signal TEXT,
    sort_order TEXT,
    feeds_watchlist INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist_entries (
    ticker TEXT PRIMARY KEY,
    source TEXT NOT NULL CHECK (source IN ('auto', 'manual')),
    added_at TEXT NOT NULL,
    last_seen_in_feeder_at TEXT,
    is_pinned INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watchlist_appearances (
    ticker TEXT NOT NULL REFERENCES watchlist_entries (ticker) ON DELETE CASCADE,
    seen_on TEXT NOT NULL,
    change_percent REAL,
    screen_id INTEGER NOT NULL,
    PRIMARY KEY (ticker, seen_on, screen_id)
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    # FastAPI may run a request's dependency and its handler on different
    # worker threads; each connection is still used by one request at a time.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
