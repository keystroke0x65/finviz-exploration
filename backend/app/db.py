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

CREATE TABLE IF NOT EXISTS bar_cache (
    ticker TEXT NOT NULL,
    interval TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    bars TEXT NOT NULL,
    PRIMARY KEY (ticker, interval)
);

CREATE TABLE IF NOT EXISTS setup_records (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    pattern TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    timeframe TEXT NOT NULL,
    entry REAL NOT NULL,
    stop REAL NOT NULL,
    capped_target REAL NOT NULL,
    target_3r REAL NOT NULL,
    available_reward_risk REAL NOT NULL,
    risk_percent REAL NOT NULL,
    blocking_level REAL,
    partial_1r REAL NOT NULL,
    partial_2r REAL NOT NULL,
    trailing_stop REAL,
    quality REAL NOT NULL,
    score REAL NOT NULL,
    score_parts TEXT NOT NULL,
    key_points TEXT NOT NULL,
    state TEXT NOT NULL,
    first_state TEXT NOT NULL,
    session TEXT NOT NULL,
    float_at_detection REAL,
    detected_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    outcome TEXT NOT NULL DEFAULT 'open',
    resolved_at TEXT,
    max_favorable_r REAL,
    max_adverse_r REAL,
    verdict TEXT
);

-- One open record per setup; once resolved, a later occurrence of the same
-- setup starts a new record instead of rewriting a finished one.
CREATE UNIQUE INDEX IF NOT EXISTS setup_records_open_key
    ON setup_records (ticker, pattern, direction, timeframe, entry)
    WHERE outcome = 'open';

CREATE TABLE IF NOT EXISTS ticker_scans (
    ticker TEXT PRIMARY KEY,
    scanned_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticker_snapshots (
    ticker TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticker_verdicts (
    ticker TEXT PRIMARY KEY,
    call TEXT NOT NULL,
    score REAL NOT NULL,
    parts TEXT NOT NULL,
    reasons TEXT NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS leaves an
# existing table untouched, so each is added to older databases here.
ADDED_COLUMNS = [
    ("setup_records", "verdict", "TEXT"),
]


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    for table, column, column_type in ADDED_COLUMNS:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            # Names come from the constant above, never from input.
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
    conn.commit()


def connect(db_path: str) -> sqlite3.Connection:
    # FastAPI may run a request's dependency and its handler on different
    # worker threads; each connection is still used by one request at a time.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _add_missing_columns(conn)
    return conn
