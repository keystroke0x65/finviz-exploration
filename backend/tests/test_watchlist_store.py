from datetime import date, datetime, timedelta, timezone

from app.watchlist.store import (
    add_manual_entry,
    expire_stale_entries,
    get_entry,
    list_entries,
    record_feeder_hit,
    remove_entry,
    set_pinned,
)

NOW = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
RETENTION_DAYS = 90
SCREEN_ID = 1
OTHER_SCREEN_ID = 2


def test_feeder_hit_adds_auto_entry_with_appearance(db_conn):
    outcome = record_feeder_hit(db_conn, "HOST", 47.4, SCREEN_ID, NOW)

    entry = get_entry(db_conn, "HOST")
    assert outcome == "added"
    assert entry.source == "auto"
    assert entry.added_at == NOW
    assert entry.last_seen_in_feeder_at == NOW
    assert entry.is_pinned is False
    assert [(a.seen_on, a.change_percent, a.screen_id) for a in entry.appearances] == [
        (date(2026, 10, 20), 47.4, SCREEN_ID)
    ]


def test_feeder_hit_twice_same_day_keeps_one_appearance(db_conn):
    record_feeder_hit(db_conn, "HOST", 10.0, SCREEN_ID, NOW)
    later = NOW + timedelta(hours=4)

    outcome = record_feeder_hit(db_conn, "HOST", 25.0, SCREEN_ID, later)

    entry = get_entry(db_conn, "HOST")
    assert outcome == "updated"
    assert len(entry.appearances) == 1
    assert entry.appearances[0].change_percent == 25.0
    assert entry.last_seen_in_feeder_at == later
    assert entry.added_at == NOW
    assert len(list_entries(db_conn)) == 1


def test_feeder_hits_from_two_screens_same_day_keep_one_each(db_conn):
    record_feeder_hit(db_conn, "HOST", 10.0, SCREEN_ID, NOW)
    record_feeder_hit(db_conn, "HOST", 11.0, OTHER_SCREEN_ID, NOW)

    entry = get_entry(db_conn, "HOST")

    assert sorted(a.screen_id for a in entry.appearances) == [SCREEN_ID, OTHER_SCREEN_ID]


def test_feeder_hits_on_different_days_list_newest_first(db_conn):
    record_feeder_hit(db_conn, "HOST", 10.0, SCREEN_ID, NOW)
    record_feeder_hit(db_conn, "HOST", 30.0, SCREEN_ID, NOW + timedelta(days=7))

    entry = get_entry(db_conn, "HOST")

    assert [a.seen_on for a in entry.appearances] == [date(2026, 10, 27), date(2026, 10, 20)]


def test_appearance_date_uses_eastern_time(db_conn):
    # 02:30 UTC on Oct 21 is 22:30 ET on Oct 20 (after-hours session).
    record_feeder_hit(db_conn, "HOST", 5.0, SCREEN_ID, datetime(2026, 10, 21, 2, 30, tzinfo=timezone.utc))

    assert get_entry(db_conn, "HOST").appearances[0].seen_on == date(2026, 10, 20)


def test_feeder_hit_keeps_manual_source(db_conn):
    add_manual_entry(db_conn, "HOST", NOW)

    record_feeder_hit(db_conn, "HOST", 5.0, SCREEN_ID, NOW + timedelta(hours=1))

    entry = get_entry(db_conn, "HOST")
    assert entry.source == "manual"
    assert entry.last_seen_in_feeder_at == NOW + timedelta(hours=1)


def test_manual_add_creates_manual_entry_without_feeder_date(db_conn):
    entry = add_manual_entry(db_conn, "HOST", NOW)

    assert entry.source == "manual"
    assert entry.added_at == NOW
    assert entry.last_seen_in_feeder_at is None
    assert entry.appearances == []


def test_manual_add_converts_auto_entry(db_conn):
    record_feeder_hit(db_conn, "HOST", 5.0, SCREEN_ID, NOW)

    entry = add_manual_entry(db_conn, "HOST", NOW + timedelta(days=1))

    assert entry.source == "manual"
    assert entry.added_at == NOW
    assert len(entry.appearances) == 1


def test_expire_removes_auto_entries_older_than_retention(db_conn):
    record_feeder_hit(db_conn, "OLD", 5.0, SCREEN_ID, NOW - timedelta(days=91))
    record_feeder_hit(db_conn, "FRESH", 5.0, SCREEN_ID, NOW - timedelta(days=89))

    expired = expire_stale_entries(db_conn, NOW, RETENTION_DAYS)

    assert expired == ["OLD"]
    assert get_entry(db_conn, "OLD") is None
    assert get_entry(db_conn, "FRESH") is not None


def test_expire_keeps_pinned_and_manual_entries(db_conn):
    long_ago = NOW - timedelta(days=200)
    record_feeder_hit(db_conn, "PINNED", 5.0, SCREEN_ID, long_ago)
    set_pinned(db_conn, "PINNED", True)
    add_manual_entry(db_conn, "MANUAL", long_ago)

    assert expire_stale_entries(db_conn, NOW, RETENTION_DAYS) == []
    assert get_entry(db_conn, "PINNED") is not None
    assert get_entry(db_conn, "MANUAL") is not None


def test_set_pinned_returns_none_for_missing_entry(db_conn):
    assert set_pinned(db_conn, "NOPE", True) is None


def test_remove_deletes_appearances_and_later_hit_re_adds_as_auto(db_conn):
    add_manual_entry(db_conn, "HOST", NOW)
    record_feeder_hit(db_conn, "HOST", 5.0, SCREEN_ID, NOW)

    assert remove_entry(db_conn, "HOST") is True
    assert get_entry(db_conn, "HOST") is None
    assert db_conn.execute("SELECT COUNT(*) FROM watchlist_appearances").fetchone()[0] == 0

    record_feeder_hit(db_conn, "HOST", 9.0, SCREEN_ID, NOW + timedelta(days=10))
    entry = get_entry(db_conn, "HOST")
    assert entry.source == "auto"
    assert len(entry.appearances) == 1


def test_remove_missing_entry_returns_false(db_conn):
    assert remove_entry(db_conn, "NOPE") is False


def test_list_orders_by_last_seen_desc_with_never_seen_last(db_conn):
    record_feeder_hit(db_conn, "OLDER", 5.0, SCREEN_ID, NOW - timedelta(days=2))
    record_feeder_hit(db_conn, "NEWER", 5.0, SCREEN_ID, NOW)
    add_manual_entry(db_conn, "AAA", NOW)

    assert [entry.ticker for entry in list_entries(db_conn)] == ["NEWER", "OLDER", "AAA"]
