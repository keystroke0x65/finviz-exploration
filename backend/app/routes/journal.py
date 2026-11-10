import sqlite3
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse

from app.cache import get_cached_quote, set_cached_quote
from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError, TickerNotFoundError
from app.finviz_client import get_bars, get_quote
from app.journal.bars import aggregate_bars, days_needed, read_bars
from app.journal.export import entries_csv, fills_csv
from app.journal.positions import Fill, compute_trade_figures, validate_fills, validate_plan
from app.journal.reasons import MISTAKES, PASS_REASON_GROUPS
from app.journal.schemas import (
    DailyLossOut,
    DaySetupOut,
    EntryBarsOut,
    EntryIn,
    JournalEntryOut,
    JournalSummaryOut,
    PassIn,
    PreviewOut,
    ReasonCatalogOut,
    TradeIn,
)
from app.journal.service import (
    EntryDraft,
    SetupNotFoundError,
    load_reviewed,
    load_trade_figures,
    prepare_entry,
    review_trade,
    score_saved_pass,
)
from app.journal.store import JournalEntry, create_entry, delete_entry, find_open_trade, get_entry, list_entries, update_entry
from app.journal.summary import Period, daily_realised_pnl, period_start, summarise
from app.routes.dependencies import get_db_connection
from app.routes.stocks import TICKER_PATTERN, TickerPath
from app.setups.store import list_setups_for_day, setup_values_at
from app.setups.track_record import stats_for
from app.user_settings import get_journal_settings

router = APIRouter(prefix="/api/journal", tags=["journal"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]
# The daily loss note turns amber at this share of the limit.
DAILY_LOSS_WARNING_SHARE = 0.8
FIVE_MINUTES = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_quote(ticker: str) -> dict | None:
    """Best effort: an entry saves without company facts when Finviz can't answer."""
    cached = get_cached_quote(ticker)
    if cached is not None:
        return cached
    try:
        quote = get_quote(ticker)
    except (TickerNotFoundError, FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError):
        return None
    set_cached_quote(ticker, quote)
    return quote


def _to_draft(body: TradeIn | PassIn, now: datetime) -> EntryDraft:
    if isinstance(body, PassIn):
        return EntryDraft("pass", body.ticker, body.direction, body.setup_record_id, None, None, 0.0, body.reasons, [],
                          body.note, [], body.decided_at)
    fills = [Fill(fill.side, fill.time, fill.price, fill.shares) for fill in body.fills]
    problem = validate_fills(body.direction, fills) or validate_plan(body.direction, fills, body.plan_stop, body.plan_target)
    if problem is None and any(fill.time > now for fill in fills):
        problem = "A fill can't be in the future."
    if problem is not None:
        raise HTTPException(status_code=422, detail=problem)
    return EntryDraft("trade", body.ticker, body.direction, body.setup_record_id, body.plan_stop, body.plan_target,
                      body.fees, [], body.mistakes, body.note, fills, None)


def _to_out(conn: sqlite3.Connection, entry: JournalEntry, now: datetime, bar_warning: str | None = None) -> JournalEntryOut:
    payload = {**asdict(entry), "figures": None, "after_exit": None, "plan_flags": [], "pass_score": None, "after_pass": None,
               "bar_warning": bar_warning}
    if entry.kind == "trade" and entry.fills:
        reviewed = review_trade(conn, entry, now)
        payload.update(figures=asdict(reviewed.figures), after_exit=reviewed.after and asdict(reviewed.after),
                       plan_flags=reviewed.flags)
    if entry.kind == "pass":
        scored = score_saved_pass(conn, entry, now)
        payload["pass_score"] = asdict(scored.score)
        payload["after_pass"] = scored.after and asdict(scored.after)
    return JournalEntryOut(**payload)


def _prepare(conn: sqlite3.Connection, body: TradeIn | PassIn, now: datetime, stored: JournalEntry | None = None):
    try:
        return prepare_entry(conn, _to_draft(body, now), now, get_bars, _load_quote, stored)
    except SetupNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/reasons", response_model=ReasonCatalogOut)
def get_reasons() -> ReasonCatalogOut:
    return ReasonCatalogOut(
        pass_reasons=[{"group": group, "items": [{"key": key, "label": label} for key, label in items]}
                      for group, items in PASS_REASON_GROUPS],
        mistakes=[{"key": key, "label": label} for key, label in MISTAKES],
    )


@router.get("/entries", response_model=list[JournalEntryOut])
def get_entries(
    conn: DbConnection,
    kind: Literal["trade", "pass"] | None = None,
    period: Period = "all",
    ticker: Annotated[str | None, Query(pattern=TICKER_PATTERN)] = None,
) -> list[JournalEntryOut]:
    now = _now()
    start = period_start(period, now)
    matching = list_entries(conn, kind, ticker.upper() if ticker else None)
    entries = [entry for entry in matching if start is None or entry.decided_at >= start]
    return [_to_out(conn, entry, now) for entry in entries]


@router.post("/entries", response_model=JournalEntryOut, status_code=201)
def post_entry(body: Annotated[EntryIn, Body()], conn: DbConnection) -> JournalEntryOut:
    now = _now()
    entry, bar_warning = _prepare(conn, body, now)
    return _to_out(conn, create_entry(conn, entry, now), now, bar_warning)


@router.get("/entries/{entry_id}", response_model=JournalEntryOut)
def get_one_entry(entry_id: int, conn: DbConnection) -> JournalEntryOut:
    entry = get_entry(conn, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    return _to_out(conn, entry, _now())


@router.put("/entries/{entry_id}", response_model=JournalEntryOut)
def put_entry(entry_id: int, body: Annotated[EntryIn, Body()], conn: DbConnection) -> JournalEntryOut:
    stored = get_entry(conn, entry_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    now = _now()
    entry, bar_warning = _prepare(conn, body, now, stored)
    updated = update_entry(conn, entry_id, entry, now)
    if updated is None:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    return _to_out(conn, updated, now, bar_warning)


@router.delete("/entries/{entry_id}", status_code=204)
def remove_entry(entry_id: int, conn: DbConnection) -> Response:
    if not delete_entry(conn, entry_id):
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    return Response(status_code=204)


@router.post("/preview", response_model=PreviewOut)
def post_preview(body: TradeIn) -> PreviewOut:
    """Figures for fills being typed; a fill problem comes back as text, not a 422."""
    fills = [Fill(fill.side, fill.time, fill.price, fill.shares) for fill in body.fills]
    problem = validate_fills(body.direction, fills) or validate_plan(body.direction, fills, body.plan_stop, body.plan_target)
    if problem is not None:
        return PreviewOut(figures=None, error=problem)
    figures = compute_trade_figures(body.direction, fills, body.plan_stop, body.plan_target, body.fees, _now())
    return PreviewOut(figures=asdict(figures), error=None)


@router.get("/entries/{entry_id}/bars", response_model=EntryBarsOut)
def get_entry_bars(entry_id: int, conn: DbConnection, interval: Literal["1m", "5m"] = "1m") -> EntryBarsOut:
    entry = get_entry(conn, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    bars, statuses = read_bars(conn, entry.ticker, days_needed(entry, _now()))
    shown = aggregate_bars(bars, FIVE_MINUTES) if interval == "5m" else bars
    return EntryBarsOut(
        bars=[asdict(bar) for bar in shown],
        days=[{"day": day, "status": status} for day, status in statuses.items()],
    )


@router.get("/setups/{ticker}", response_model=list[DaySetupOut])
def get_day_setups(ticker: TickerPath, day: date, at: datetime, conn: DbConnection) -> list[DaySetupOut]:
    """The stock's setups that day, each as it looked at `at` (for the setup picker)."""
    rows = []
    for record in list_setups_for_day(conn, ticker.upper(), day):
        values = setup_values_at(conn, record.id, at)
        rows.append(DaySetupOut(
            setup_record_id=record.id, pattern=record.pattern, timeframe=record.timeframe, direction=record.direction,
            entry=record.entry, stop=record.stop, target=record.capped_target, reward_risk=record.available_reward_risk,
            score=values.score, state=values.state, verdict=values.verdict,
            sliding_scale=values.sliding_scale and asdict(values.sliding_scale), outcome=record.outcome,
        ))
    return rows


@router.get("/open-trade/{ticker}", response_model=JournalEntryOut | None)
def get_open_trade(ticker: TickerPath, conn: DbConnection) -> JournalEntryOut | None:
    now = _now()
    entry = find_open_trade(conn, ticker.upper(), now)
    return None if entry is None else _to_out(conn, entry, now)


def _system_stats(conn: sqlite3.Connection):
    return lambda pattern, timeframe: stats_for(conn, pattern, timeframe)


@router.get("/summary", response_model=JournalSummaryOut)
def get_summary(conn: DbConnection, period: Period = "week") -> JournalSummaryOut:
    now = _now()
    start = period_start(period, now)
    trades, passes = load_reviewed(conn, now, start)
    summary = asdict(summarise(trades, passes, start, _system_stats(conn)))
    # The track record's response shape also says whether the history is trusted.
    for row in summary["versus_system"]:
        if row["system"] is not None:
            row["system"]["has_enough_history"] = row["system_has_enough_history"]
    return JournalSummaryOut(**summary)


@router.get("/daily-loss", response_model=DailyLossOut)
def get_daily_loss(conn: DbConnection) -> DailyLossOut:
    now = _now()
    pnl = daily_realised_pnl(load_trade_figures(conn, now), now)
    limit = get_journal_settings(conn)["max_daily_loss"]
    level: Literal["ok", "warning", "reached"] = "ok"
    if limit is not None and -pnl >= limit:
        level = "reached"
    elif limit is not None and -pnl >= limit * DAILY_LOSS_WARNING_SHARE:
        level = "warning"
    return DailyLossOut(realised_pnl_today=pnl, max_daily_loss=limit, level=level)


def _csv_response(text: str, filename: str) -> PlainTextResponse:
    return PlainTextResponse(
        text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


def _period_entries(conn: sqlite3.Connection, period: Period):
    now = _now()
    start = period_start(period, now)
    trades, passes = load_reviewed(conn, now, start)
    in_period = [trade for trade in trades if start is None or trade.figures.last_fill_at >= start]
    passed = [scored for scored in passes if start is None or scored.entry.decided_at >= start]
    return in_period, passed


@router.get("/export/entries.csv")
def export_entries(conn: DbConnection, period: Period = "all") -> PlainTextResponse:
    trades, passes = _period_entries(conn, period)
    return _csv_response(entries_csv(trades, passes), f"journal-entries-{period}.csv")


@router.get("/export/fills.csv")
def export_fills(conn: DbConnection, period: Period = "all") -> PlainTextResponse:
    trades, _ = _period_entries(conn, period)
    return _csv_response(fills_csv(trades), f"journal-fills-{period}.csv")
