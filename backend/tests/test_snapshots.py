import json
from datetime import datetime

from app.market_time import EASTERN
from app.scanning.snapshots import read_snapshots, save_snapshots
from tests.scan_fixtures import snapshot

NOW = datetime(2026, 10, 26, 15, 15, tzinfo=EASTERN)
NEWS_TIME = datetime(2026, 10, 22, 11, 0, tzinfo=EASTERN)


def test_snapshot_with_a_news_time_round_trips(db_conn):
    row = snapshot("HOST", news_time=NEWS_TIME)

    save_snapshots(db_conn, [row], NOW)

    assert read_snapshots(db_conn)["HOST"] == (row, NOW)


def test_snapshot_saved_before_news_times_were_parsed_reads_as_eastern(db_conn):
    # Rows saved before 2026-10-26 hold Finviz's raw "YYYY-MM-DD HH:MM:SS" text.
    stored = {**json.loads(json.dumps(snapshot("HOST", news_time=None).__dict__)), "news_time": "2026-10-22 11:00:00"}
    db_conn.execute(
        "INSERT INTO ticker_snapshots (ticker, data, fetched_at) VALUES (?, ?, ?)",
        ("HOST", json.dumps(stored), NOW.isoformat()),
    )

    restored, _ = read_snapshots(db_conn)["HOST"]

    assert restored.news_time == NEWS_TIME
