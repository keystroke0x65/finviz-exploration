from datetime import datetime, timedelta

from app.journal.positions import Fill
from app.journal.reasons import MISTAKE_KEYS, OTHER_REASON, PASS_REASON_GROUPS, PASS_REASON_KEYS
from app.journal.store import (
    NewEntry,
    SetupSnapshot,
    StockFacts,
    create_entry,
    delete_entry,
    find_open_trade,
    get_entry,
    list_entries,
    update_entry,
)
from app.market_time import EASTERN
from app.patterns.sliding_scale import Factor, SlidingScale

NOW = datetime(2026, 11, 9, 11, 0, tzinfo=EASTERN)
ENTRY_TIME = datetime(2026, 11, 9, 9, 45, tzinfo=EASTERN)
FACTS = StockFacts(
    company="Host Corp", country="USA", sector="Technology", industry="Software", market_cap_millions=32.4,
    float_millions=5.5, price=1.84, change_percent=12.5, volume_so_far=1_234_000, volume_vs_average=3.1,
)
SETUP = SetupSnapshot(
    setup_record_id=None, pattern="bull_flag", timeframe="1m", direction="long", entry=1.84, stop=1.76,
    target=2.08, reward_risk=3.0, score=93.0, state="forming", verdict="leans_long",
    sliding_scale=SlidingScale("C", 8, [Factor("price", "good", "Under $20")]),
)


def trade(fills=None, ticker="HOST", decided_at=ENTRY_TIME, mistakes=None):
    return NewEntry(
        kind="trade", ticker=ticker, direction="long", decided_at=decided_at, setup=SETUP, stock=FACTS,
        plan_stop=1.76, plan_target=2.08, fees=0.0, reasons=[], mistakes=mistakes or ["chased"], note="quick one",
        pass_price=None,
        fills=fills if fills is not None else [Fill("buy", ENTRY_TIME, 1.84, 500), Fill("sell", NOW, 2.0, 500)],
    )


def a_pass(decided_at=ENTRY_TIME):
    return NewEntry(
        kind="pass", ticker="HOST", direction="long", decided_at=decided_at, setup=None, stock=FACTS,
        plan_stop=None, plan_target=None, fees=0.0, reasons=["low_sykes", "too_late"], mistakes=[], note="",
        pass_price=1.9, fills=[],
    )


def test_create_and_get_round_trip(db_conn):
    created = create_entry(db_conn, trade(), NOW)

    loaded = get_entry(db_conn, created.id)

    assert loaded == created
    assert loaded.kind == "trade"
    assert loaded.setup == SETUP
    assert loaded.stock == FACTS
    assert loaded.fills == [Fill("buy", ENTRY_TIME, 1.84, 500), Fill("sell", NOW, 2.0, 500)]
    assert loaded.mistakes == ["chased"]
    assert loaded.created_at == NOW


def test_pass_keeps_reasons_and_price(db_conn):
    created = create_entry(db_conn, a_pass(), NOW)

    assert (created.reasons, created.pass_price, created.setup, created.fills) == (["low_sykes", "too_late"], 1.9, None, [])


def test_update_replaces_fills_and_keeps_created_time(db_conn):
    created = create_entry(db_conn, trade(), NOW)
    later = NOW + timedelta(minutes=5)

    updated = update_entry(db_conn, created.id, trade(fills=[Fill("buy", ENTRY_TIME, 1.85, 100)]), later)

    assert updated.fills == [Fill("buy", ENTRY_TIME, 1.85, 100)]
    assert (updated.created_at, updated.updated_at) == (NOW, later)


def test_update_missing_entry_returns_none(db_conn):
    assert update_entry(db_conn, 999, trade(), NOW) is None


def test_delete_removes_entry_and_fills(db_conn):
    created = create_entry(db_conn, trade(), NOW)

    assert delete_entry(db_conn, created.id) is True
    assert get_entry(db_conn, created.id) is None
    assert db_conn.execute("SELECT COUNT(*) FROM journal_fills").fetchone()[0] == 0
    assert delete_entry(db_conn, created.id) is False


def test_list_orders_newest_first_and_filters_by_kind(db_conn):
    older = create_entry(db_conn, trade(decided_at=ENTRY_TIME - timedelta(days=1)), NOW)
    newer = create_entry(db_conn, a_pass(decided_at=ENTRY_TIME), NOW)

    assert [entry.id for entry in list_entries(db_conn)] == [newer.id, older.id]
    assert [entry.id for entry in list_entries(db_conn, kind="trade")] == [older.id]


def test_find_open_trade_ignores_closed_trades(db_conn):
    create_entry(db_conn, trade(), NOW)
    open_trade = create_entry(db_conn, trade(fills=[Fill("buy", ENTRY_TIME, 1.84, 500)]), NOW)
    create_entry(db_conn, trade(ticker="OTHER", fills=[Fill("buy", ENTRY_TIME, 3.0, 10)]), NOW)

    assert find_open_trade(db_conn, "HOST", NOW).id == open_trade.id


def test_find_open_trade_none_when_all_closed(db_conn):
    create_entry(db_conn, trade(), NOW)

    assert find_open_trade(db_conn, "HOST", NOW) is None


def test_reason_keys_are_unique_and_include_other():
    keys = [key for _, items in PASS_REASON_GROUPS for key, _ in items]

    assert len(keys) == len(set(keys)) == len(PASS_REASON_KEYS)
    assert OTHER_REASON in PASS_REASON_KEYS
    assert "low_sykes" in PASS_REASON_KEYS
    assert "followed_plan" in MISTAKE_KEYS
