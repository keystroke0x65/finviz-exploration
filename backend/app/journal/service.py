"""Builds journal entries from validated drafts and reviews saved ones.

Network access comes in as functions (fetch bars, load a quote) so this module
can be tested without Finviz.
"""

import logging
import sqlite3
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from typing import Callable

from app.bars.loader import FetchBars, load_bars
from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import Bar
from app.journal.bars import days_needed, read_bars, save_bars_for_entry
from app.journal.pass_scoring import score_pass
from app.journal.positions import Direction, Fill, compute_trade_figures
from app.journal.review import after_exit, plan_flags
from app.journal.snapshot import previous_close, setup_snapshot, stock_facts_at
from app.journal.store import EMPTY_FACTS, EntryKind, JournalEntry, NewEntry, StockFacts, list_entries
from app.journal.summary import ReviewedTrade, ScoredPass
from app.market_time import EASTERN
from app.scanning.snapshots import read_snapshots
from app.setups.store import get_setup_record, setup_values_at

logger = logging.getLogger(__name__)

LoadQuote = Callable[[str], dict | None]
FINVIZ_ERRORS = (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError)


class SetupNotFoundError(ValueError):
    def __init__(self, setup_record_id: int):
        super().__init__(f"Setup not found (id {setup_record_id}).")


@dataclass(frozen=True)
class EntryDraft:
    kind: EntryKind
    ticker: str
    direction: Direction
    setup_record_id: int | None
    plan_stop: float | None
    plan_target: float | None
    fees: float
    reasons: list[str]
    mistakes: list[str]
    note: str
    fills: list[Fill]
    # Passes only: when the user passed (None = now).
    decided_at: datetime | None


def _decided_at(draft: EntryDraft, now: datetime) -> datetime:
    if draft.kind == "trade":
        return min(fill.time for fill in draft.fills)
    return draft.decided_at or now


def _base_entry(conn: sqlite3.Connection, draft: EntryDraft, decided_at: datetime) -> NewEntry:
    setup = None
    if draft.setup_record_id is not None:
        record = get_setup_record(conn, draft.setup_record_id)
        if record is None:
            raise SetupNotFoundError(draft.setup_record_id)
        setup = setup_snapshot(record, setup_values_at(conn, record.id, decided_at))
    return NewEntry(
        kind=draft.kind, ticker=draft.ticker, direction=draft.direction, decided_at=decided_at, setup=setup,
        stock=EMPTY_FACTS, plan_stop=draft.plan_stop, plan_target=draft.plan_target, fees=draft.fees,
        reasons=draft.reasons, mistakes=draft.mistakes, note=draft.note, pass_price=None, fills=draft.fills,
    )


def _previous_close(conn: sqlite3.Connection, ticker: str, day: date, now: datetime, fetch_bars_fn: FetchBars) -> float | None:
    try:
        daily = load_bars(conn, ticker, "daily", now, fetch_bars_fn).bars
    except FINVIZ_ERRORS as exc:
        logger.warning("no previous close for %s: %s", ticker, exc)
        return None
    return previous_close(daily, day)


def _keep_known(fresh: StockFacts, stored: StockFacts | None) -> StockFacts:
    """On an edit, a fact the new lookup couldn't get (Finviz down) keeps its saved value."""
    if stored is None:
        return fresh
    return StockFacts(**{
        name: value if value is not None else getattr(stored, name) for name, value in asdict(fresh).items()
    })


def prepare_entry(
    conn: sqlite3.Connection,
    draft: EntryDraft,
    now: datetime,
    fetch_bars_fn: FetchBars,
    load_quote: LoadQuote,
    stored: NewEntry | None = None,
) -> tuple[NewEntry, str | None]:
    """The entry to store, with setup and stock as they were at decided_at, plus any bar warning.

    `stored` is the saved entry when editing. Raises SetupNotFoundError for an unknown setup id.
    """
    decided_at = _decided_at(draft, now)
    entry = _base_entry(conn, draft, decided_at)
    bar_warning = save_bars_for_entry(conn, entry, now, fetch_bars_fn)
    day = decided_at.astimezone(EASTERN).date()
    bars, _ = read_bars(conn, entry.ticker, [day])
    snapshot_row = read_snapshots(conn).get(entry.ticker)
    close_before = _previous_close(conn, entry.ticker, day, now, fetch_bars_fn)
    facts = stock_facts_at(bars, close_before, decided_at, load_quote(entry.ticker), snapshot_row[0] if snapshot_row else None)
    if entry.kind == "trade":
        # The trade's own first fill is the price that mattered, not the bar's close.
        price = min(entry.fills, key=lambda fill: fill.time).price
        change = (price / close_before - 1) * 100 if close_before else None
        trade_facts = replace(facts, price=price, change_percent=change)
        return replace(entry, stock=_keep_known(trade_facts, stored and stored.stock)), bar_warning
    pass_facts = _keep_known(facts, stored and stored.stock)
    return replace(entry, stock=pass_facts, pass_price=pass_facts.price), bar_warning


def _entry_bars(conn: sqlite3.Connection, entry: JournalEntry, now: datetime) -> list[Bar]:
    bars, _ = read_bars(conn, entry.ticker, days_needed(entry, now))
    return bars


def review_trade(conn: sqlite3.Connection, entry: JournalEntry, now: datetime) -> ReviewedTrade:
    figures = compute_trade_figures(entry.direction, entry.fills, entry.plan_stop, entry.plan_target, entry.fees, now)
    bars = _entry_bars(conn, entry, now)
    return ReviewedTrade(
        entry=entry,
        figures=figures,
        after=after_exit(entry.direction, figures, entry.plan_stop, bars),
        flags=plan_flags(entry.direction, figures, entry.plan_stop, entry.plan_target, entry.fills, bars),
    )


def _price_at(bars: list[Bar], moment: datetime) -> float | None:
    earlier = [bar for bar in bars if bar.time <= moment]
    return earlier[-1].close if earlier else None


def score_saved_pass(conn: sqlite3.Connection, entry: JournalEntry, now: datetime) -> ScoredPass:
    bars = _entry_bars(conn, entry, now)
    # A pass saved while Finviz was down has no price; once the bars arrive, take it from them.
    # Without it the pass would be judged from the setup's ideal entry, overstating a "missed it".
    pass_price = entry.pass_price if entry.pass_price is not None else _price_at(bars, entry.decided_at)
    return ScoredPass(entry, score_pass(entry.setup, entry.decided_at, pass_price, bars))


def load_reviewed(conn: sqlite3.Connection, now: datetime) -> tuple[list[ReviewedTrade], list[ScoredPass]]:
    entries = list_entries(conn)
    trades = [review_trade(conn, entry, now) for entry in entries if entry.kind == "trade" and entry.fills]
    passes = [score_saved_pass(conn, entry, now) for entry in entries if entry.kind == "pass"]
    return trades, passes
