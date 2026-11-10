"""CSV files of journal entries and fills, safe to open in a spreadsheet."""

import csv
import io
from datetime import datetime

from app.journal.store import JournalEntry
from app.journal.summary import ReviewedTrade, ScoredPass

# A spreadsheet runs a cell starting with these as a formula (CSV injection).
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")

ENTRY_COLUMNS = [
    "id", "kind", "ticker", "direction", "decided_at", "pattern", "timeframe", "score", "sykes_grade",
    "sykes_points", "status", "average_entry", "average_exit", "max_shares", "money_in", "fees", "net_pnl",
    "r_multiple", "planned_reward_risk", "duration_minutes", "plan_stop", "plan_target", "mistakes", "reasons",
    "pass_price", "pass_outcome", "country", "industry", "note",
]
FILL_COLUMNS = ["entry_id", "ticker", "side", "time", "price", "shares"]


def escape_cell(value: object) -> str:
    """Text that a spreadsheet would run as a formula gets a leading quote; numbers stay numbers."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value)
    return f"'{value}" if value.startswith(FORMULA_STARTS) else value


def _write(columns: list[str], rows: list[dict[str, object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([escape_cell(row.get(column)) for column in columns])
    return buffer.getvalue()


def _common(entry: JournalEntry) -> dict[str, object]:
    setup = entry.setup
    scale = setup.sliding_scale if setup else None
    return {
        "id": entry.id, "kind": entry.kind, "ticker": entry.ticker, "direction": entry.direction,
        "decided_at": entry.decided_at.isoformat(), "pattern": setup.pattern if setup else None,
        "timeframe": setup.timeframe if setup else None, "score": setup.score if setup else None,
        "sykes_grade": scale.letter if scale else None, "sykes_points": scale.points if scale else None,
        "plan_stop": entry.plan_stop, "plan_target": entry.plan_target, "mistakes": ";".join(entry.mistakes),
        "reasons": ";".join(entry.reasons), "country": entry.stock.country, "industry": entry.stock.industry,
        "note": entry.note,
    }


def entries_csv(trades: list[ReviewedTrade], passes: list[ScoredPass]) -> str:
    rows: list[tuple[datetime, dict[str, object]]] = []
    for trade in trades:
        figures = trade.figures
        rows.append((trade.entry.decided_at, {
            **_common(trade.entry), "status": figures.status, "average_entry": figures.average_entry,
            "average_exit": figures.average_exit, "max_shares": figures.max_shares, "money_in": figures.money_in,
            "fees": figures.fees, "net_pnl": figures.net_pnl, "r_multiple": figures.r_multiple,
            "planned_reward_risk": figures.planned_reward_risk,
            "duration_minutes": round(figures.duration_seconds / 60, 1),
        }))
    for scored in passes:
        rows.append((scored.entry.decided_at, {
            **_common(scored.entry), "pass_price": scored.entry.pass_price, "pass_outcome": scored.score.outcome,
        }))
    # Sorted as datetimes: stored times carry different UTC offsets, so their text doesn't sort by time.
    newest_first = sorted(rows, key=lambda item: item[0], reverse=True)
    return _write(ENTRY_COLUMNS, [row for _, row in newest_first])


def fills_csv(trades: list[ReviewedTrade]) -> str:
    rows = [
        {"entry_id": trade.entry.id, "ticker": trade.entry.ticker, "side": fill.side, "time": fill.time.isoformat(),
         "price": fill.price, "shares": fill.shares}
        for trade in trades
        for fill in trade.entry.fills
    ]
    return _write(FILL_COLUMNS, rows)
