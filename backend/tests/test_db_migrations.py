import sqlite3

from app.db import connect

M2A_SETUP_RECORDS = """
CREATE TABLE setup_records (
    id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, pattern TEXT NOT NULL, direction TEXT NOT NULL,
    timeframe TEXT NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL, capped_target REAL NOT NULL,
    target_3r REAL NOT NULL, available_reward_risk REAL NOT NULL, risk_percent REAL NOT NULL,
    blocking_level REAL, partial_1r REAL NOT NULL, partial_2r REAL NOT NULL, trailing_stop REAL,
    quality REAL NOT NULL, score REAL NOT NULL, score_parts TEXT NOT NULL, key_points TEXT NOT NULL,
    state TEXT NOT NULL, first_state TEXT NOT NULL, session TEXT NOT NULL, float_at_detection REAL,
    detected_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, outcome TEXT NOT NULL DEFAULT 'open',
    resolved_at TEXT, max_favorable_r REAL, max_adverse_r REAL
)
"""


def test_connect_adds_verdict_column_to_existing_setup_records(tmp_path):
    db_path = str(tmp_path / "m2a.db")
    old = sqlite3.connect(db_path)
    old.execute(M2A_SETUP_RECORDS)
    old.execute(
        "INSERT INTO setup_records (ticker, pattern, direction, timeframe, entry, stop, capped_target, target_3r, "
        "available_reward_risk, risk_percent, partial_1r, partial_2r, quality, score, score_parts, key_points, "
        "state, first_state, session, detected_at, last_seen_at) VALUES "
        "('HOST','bull_flag','long','5m',2,1.9,2.3,2.3,3,5,2.1,2.2,0.7,70,'{}','[]','forming','forming','regular',"
        "'2026-10-21T09:00:00-04:00','2026-10-21T09:00:00-04:00')"
    )
    old.commit()
    old.close()

    conn = connect(db_path)

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(setup_records)")}
    assert "verdict" in columns
    assert conn.execute("SELECT ticker, verdict FROM setup_records").fetchone()[:] == ("HOST", None)
    conn.close()


def test_connect_twice_is_harmless(tmp_path):
    db_path = str(tmp_path / "fresh.db")
    connect(db_path).close()

    conn = connect(db_path)

    assert [row["name"] for row in conn.execute("PRAGMA table_info(setup_records)")].count("verdict") == 1
    conn.close()
