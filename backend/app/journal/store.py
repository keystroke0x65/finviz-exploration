"""SQLite storage for journal entries (trades and passes) and their fills."""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

from app.journal.positions import Direction, Fill, compute_trade_figures
from app.patterns.sliding_scale import SlidingScale
from app.setups.store import decode_sliding_scale, encode_sliding_scale

EntryKind = Literal["trade", "pass"]


@dataclass(frozen=True)
class SetupSnapshot:
    """A setup as it looked when the user traded or passed."""

    # None once the setup record itself is gone.
    setup_record_id: int | None
    pattern: str
    timeframe: str
    direction: str
    entry: float
    stop: float
    target: float
    reward_risk: float
    score: float
    state: str
    verdict: str | None
    sliding_scale: SlidingScale | None


@dataclass(frozen=True)
class StockFacts:
    company: str | None
    country: str | None
    sector: str | None
    industry: str | None
    market_cap_millions: float | None
    float_millions: float | None
    price: float | None
    change_percent: float | None
    volume_so_far: int | None
    # Volume so far that day / average daily volume, not scaled for time of day.
    volume_vs_average: float | None


EMPTY_FACTS = StockFacts(None, None, None, None, None, None, None, None, None, None)


@dataclass(frozen=True)
class NewEntry:
    kind: EntryKind
    ticker: str
    direction: Direction
    # First fill's time for a trade; when the user passed for a pass.
    decided_at: datetime
    setup: SetupSnapshot | None
    stock: StockFacts
    plan_stop: float | None
    plan_target: float | None
    fees: float
    reasons: list[str]
    mistakes: list[str]
    note: str
    pass_price: float | None
    fills: list[Fill]


@dataclass(frozen=True)
class JournalEntry(NewEntry):
    id: int
    created_at: datetime
    updated_at: datetime


def _encode_setup(setup: SetupSnapshot | None) -> str | None:
    if setup is None:
        return None
    fields = {key: value for key, value in asdict(setup).items() if key != "sliding_scale"}
    return json.dumps({**fields, "sliding_scale": encode_sliding_scale(setup.sliding_scale)})


def _decode_setup(stored: str | None, setup_record_id: int | None) -> SetupSnapshot | None:
    if stored is None:
        return None
    payload = json.loads(stored)
    payload["sliding_scale"] = decode_sliding_scale(payload["sliding_scale"])
    payload["setup_record_id"] = setup_record_id
    return SetupSnapshot(**payload)


def _read_fills(conn: sqlite3.Connection, entry_id: int) -> list[Fill]:
    rows = conn.execute("SELECT * FROM journal_fills WHERE entry_id = ? ORDER BY time, id", (entry_id,))
    return [Fill(row["side"], datetime.fromisoformat(row["time"]), row["price"], row["shares"]) for row in rows]


def _to_entry(conn: sqlite3.Connection, row: sqlite3.Row, fills: list[Fill] | None = None) -> JournalEntry:
    return JournalEntry(
        id=row["id"],
        kind=row["kind"],
        ticker=row["ticker"],
        direction=row["direction"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        decided_at=datetime.fromisoformat(row["decided_at"]),
        setup=_decode_setup(row["setup"], row["setup_record_id"]),
        stock=StockFacts(**json.loads(row["stock"])),
        plan_stop=row["plan_stop"],
        plan_target=row["plan_target"],
        fees=row["fees"],
        reasons=json.loads(row["reasons"]),
        mistakes=json.loads(row["mistakes"]),
        note=row["note"],
        pass_price=row["pass_price"],
        fills=_read_fills(conn, row["id"]) if fills is None else fills,
    )


def _entry_values(entry: NewEntry) -> tuple:
    return (
        entry.kind, entry.ticker, entry.direction, entry.decided_at.isoformat(),
        entry.setup.setup_record_id if entry.setup else None, _encode_setup(entry.setup),
        json.dumps(asdict(entry.stock)), entry.plan_stop, entry.plan_target, entry.fees,
        json.dumps(entry.reasons), json.dumps(entry.mistakes), entry.note, entry.pass_price,
    )


def _write_fills(conn: sqlite3.Connection, entry_id: int, fills: list[Fill]) -> None:
    conn.execute("DELETE FROM journal_fills WHERE entry_id = ?", (entry_id,))
    conn.executemany(
        "INSERT INTO journal_fills (entry_id, side, time, price, shares) VALUES (?, ?, ?, ?, ?)",
        [(entry_id, fill.side, fill.time.isoformat(), fill.price, fill.shares) for fill in fills],
    )


def create_entry(conn: sqlite3.Connection, entry: NewEntry, now: datetime) -> JournalEntry:
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO journal_entries (
                kind, ticker, direction, decided_at, setup_record_id, setup, stock, plan_stop, plan_target,
                fees, reasons, mistakes, note, pass_price, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*_entry_values(entry), now.isoformat(), now.isoformat()),
        )
        entry_id = cursor.lastrowid
        _write_fills(conn, entry_id, entry.fills)
    return get_entry(conn, entry_id)


def update_entry(conn: sqlite3.Connection, entry_id: int, entry: NewEntry, now: datetime) -> JournalEntry | None:
    with conn:
        cursor = conn.execute(
            """
            UPDATE journal_entries SET
                kind = ?, ticker = ?, direction = ?, decided_at = ?, setup_record_id = ?, setup = ?, stock = ?,
                plan_stop = ?, plan_target = ?, fees = ?, reasons = ?, mistakes = ?, note = ?, pass_price = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (*_entry_values(entry), now.isoformat(), entry_id),
        )
        if cursor.rowcount == 0:
            return None
        _write_fills(conn, entry_id, entry.fills)
    return get_entry(conn, entry_id)


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    with conn:
        cursor = conn.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
    return cursor.rowcount > 0


def get_entry(conn: sqlite3.Connection, entry_id: int) -> JournalEntry | None:
    row = conn.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,)).fetchone()
    return None if row is None else _to_entry(conn, row)


def _fills_by_entry(conn: sqlite3.Connection, entry_ids: list[int]) -> dict[int, list[Fill]]:
    """Every listed entry's fills in one query, instead of one query per entry."""
    fills: dict[int, list[Fill]] = {entry_id: [] for entry_id in entry_ids}
    if not entry_ids:
        return fills
    placeholders = ",".join("?" for _ in entry_ids)
    # Only "?" placeholders are joined in; the ids themselves are bound parameters.
    rows = conn.execute(
        f"SELECT * FROM journal_fills WHERE entry_id IN ({placeholders}) ORDER BY time, id", entry_ids
    )
    for row in rows:
        fills[row["entry_id"]].append(Fill(row["side"], datetime.fromisoformat(row["time"]), row["price"], row["shares"]))
    return fills


def list_entries(
    conn: sqlite3.Connection, kind: EntryKind | None = None, ticker: str | None = None
) -> list[JournalEntry]:
    rows = conn.execute(
        "SELECT * FROM journal_entries WHERE (? IS NULL OR kind = ?) AND (? IS NULL OR ticker = ?)",
        (kind, kind, ticker, ticker),
    ).fetchall()
    fills = _fills_by_entry(conn, [row["id"] for row in rows])
    entries = [_to_entry(conn, row, fills[row["id"]]) for row in rows]
    # Sorted in Python: stored times carry different UTC offsets, so string order isn't time order.
    return sorted(entries, key=lambda entry: (entry.decided_at, entry.id), reverse=True)


def find_open_trade(conn: sqlite3.Connection, ticker: str, now: datetime) -> JournalEntry | None:
    """The stock's most recent trade that still holds shares."""
    for entry in list_entries(conn, kind="trade", ticker=ticker):
        if not entry.fills:
            continue
        figures = compute_trade_figures(entry.direction, entry.fills, entry.plan_stop, entry.plan_target, entry.fees, now)
        if figures.status == "open":
            return entry
    return None
