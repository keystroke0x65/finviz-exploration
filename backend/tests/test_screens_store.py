from datetime import datetime, timedelta, timezone

from app.screens.finviz_url import ScreenCriteria
from app.screens.store import (
    ScreenInput,
    create_screen,
    delete_screen,
    get_screen,
    list_feeder_screens,
    list_screens,
    seed_default_screens,
    update_screen,
)

NOW = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(hours=1)

LOW_FLOAT = ScreenInput(
    name="Low float",
    criteria=ScreenCriteria(["geo_usa", "sh_float_u10"], "ta_topgainers", "-change"),
    feeds_watchlist=True,
)


def test_create_then_get_round_trips_criteria(db_conn):
    created = create_screen(db_conn, LOW_FLOAT, NOW)

    fetched = get_screen(db_conn, created.id)

    assert fetched == created
    assert fetched.name == "Low float"
    assert fetched.criteria == LOW_FLOAT.criteria
    assert fetched.feeds_watchlist is True
    assert fetched.created_at == NOW
    assert fetched.updated_at == NOW


def test_get_missing_screen_returns_none(db_conn):
    assert get_screen(db_conn, 999) is None


def test_update_changes_fields_and_updated_at(db_conn):
    created = create_screen(db_conn, LOW_FLOAT, NOW)
    changed = ScreenInput(
        name="After-hours", criteria=ScreenCriteria(["geo_usa"], None, None), feeds_watchlist=False
    )

    updated = update_screen(db_conn, created.id, changed, LATER)

    assert updated.name == "After-hours"
    assert updated.criteria == ScreenCriteria(["geo_usa"], None, None)
    assert updated.feeds_watchlist is False
    assert updated.created_at == NOW
    assert updated.updated_at == LATER
    assert get_screen(db_conn, created.id) == updated


def test_update_missing_screen_returns_none(db_conn):
    assert update_screen(db_conn, 999, LOW_FLOAT, NOW) is None


def test_delete_removes_screen(db_conn):
    created = create_screen(db_conn, LOW_FLOAT, NOW)

    assert delete_screen(db_conn, created.id) is True
    assert get_screen(db_conn, created.id) is None


def test_delete_returns_false_for_missing(db_conn):
    assert delete_screen(db_conn, 999) is False


def test_list_screens_orders_by_id(db_conn):
    first = create_screen(db_conn, LOW_FLOAT, NOW)
    second = create_screen(db_conn, LOW_FLOAT, NOW)

    assert [screen.id for screen in list_screens(db_conn)] == [first.id, second.id]


def test_list_feeder_screens_only_returns_feeders(db_conn):
    feeder = create_screen(db_conn, LOW_FLOAT, NOW)
    create_screen(
        db_conn,
        ScreenInput(name="Not feeder", criteria=LOW_FLOAT.criteria, feeds_watchlist=False),
        NOW,
    )

    assert [screen.id for screen in list_feeder_screens(db_conn)] == [feeder.id]


def test_seed_creates_two_default_screens(db_conn):
    seed_default_screens(db_conn, NOW)

    screens = list_screens(db_conn)

    assert [screen.name for screen in screens] == ["Top gainers — low float", "After-hours"]
    assert screens[0].criteria == ScreenCriteria(
        ["geo_usa", "sh_price_u20", "sh_float_u10"], "ta_topgainers", "-change"
    )
    assert screens[0].feeds_watchlist is True
    assert screens[1].criteria == ScreenCriteria(
        ["geo_usa", "sh_price_u20", "sh_float_u20", "cap_largeunder"], None, None
    )
    assert screens[1].feeds_watchlist is False


def test_seed_twice_does_not_duplicate(db_conn):
    seed_default_screens(db_conn, NOW)
    seed_default_screens(db_conn, NOW)

    assert len(list_screens(db_conn)) == 2


def test_seed_does_not_recreate_after_user_deletes_all(db_conn):
    seed_default_screens(db_conn, NOW)
    for screen in list_screens(db_conn):
        delete_screen(db_conn, screen.id)

    seed_default_screens(db_conn, NOW)

    assert list_screens(db_conn) == []
