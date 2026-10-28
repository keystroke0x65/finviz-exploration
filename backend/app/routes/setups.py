import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.routes.dependencies import get_db_connection
from app.routes.stocks import TickerPath
from app.config import get_settings
from app.scanning.lock import try_scan_lock
from app.scanning.run_status import (
    CompletedScan,
    CrashedScan,
    ScanAttempt,
    is_scan_overdue,
    read_scan_status,
    save_scan_attempt,
)
from app.scanning.scanner import finviz_scan_deps, run_scan
from app.patterns.types import TIMEFRAME_ORDER
from app.patterns.verdict import Verdict
from app.scanning.verdicts import read_verdicts
from app.schemas import (
    CompletedScanOut,
    CrashedScanOut,
    ScanIn,
    ScanOut,
    ScanStatusOut,
    SetupOut,
    SetupsOut,
    TrackRecordSummaryOut,
    VerdictOut,
    WarningOut,
)
from app.setups.store import SetupRecord, list_current_setups
from app.setups.track_record import PatternStats, has_enough_history, stats_for
from app.user_settings import get_show_short_setups

router = APIRouter(prefix="/api", tags=["setups"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]


@router.post("/scans", response_model=ScanOut)
def post_scan(body: ScanIn, conn: DbConnection) -> ScanOut:
    # Runs synchronously: a full watchlist scan of up to 40 active tickers
    # takes about two minutes at Finviz's one-request-per-second pacing.
    tickers = [body.ticker.upper()] if body.ticker else None
    # Only full scans count as "the last scan"; one stock says nothing about the rest.
    is_full_scan = tickers is None
    with try_scan_lock() as is_acquired:
        if not is_acquired:
            raise HTTPException(status_code=409, detail="A scan is already running; try again when it finishes")
        now = datetime.now(timezone.utc)
        try:
            # A one-stock scan is someone wanting the latest move, so it skips the
            # bar cache; full scans keep it to stay within Finviz's rate limit.
            result = run_scan(
                conn, now, finviz_scan_deps(), tickers=tickers, should_refresh_intraday=not is_full_scan
            )
        except Exception as error:
            if is_full_scan:
                save_scan_attempt(conn, CrashedScan(finished_at=now, error_type=type(error).__name__))
            raise
    if is_full_scan:
        save_scan_attempt(
            conn, CompletedScan(finished_at=result.scanned_at, scanned=len(result.scanned), failed=result.failed)
        )
    return ScanOut(
        scanned=result.scanned,
        failed=[{"ticker": ticker, "reason": reason} for ticker, reason in result.failed],
        setups_found=result.setups_found,
        scanned_at=result.scanned_at,
    )


def _to_scan_attempt_out(attempt: ScanAttempt | None) -> CompletedScanOut | CrashedScanOut | None:
    if attempt is None:
        return None
    if isinstance(attempt, CrashedScan):
        return CrashedScanOut(finished_at=attempt.finished_at, error_type=attempt.error_type)
    return CompletedScanOut(
        finished_at=attempt.finished_at,
        scanned=attempt.scanned,
        failed=[{"ticker": ticker, "reason": reason} for ticker, reason in attempt.failed],
    )


@router.get("/scans/status", response_model=ScanStatusOut)
def get_scan_status(conn: DbConnection) -> ScanStatusOut:
    status = read_scan_status(conn)
    interval = timedelta(minutes=get_settings().feeder_interval_minutes)
    return ScanStatusOut(
        latest=_to_scan_attempt_out(status.latest),
        last_completed_at=status.last_completed_at,
        is_overdue=is_scan_overdue(status.last_completed_at, datetime.now(timezone.utc), interval),
    )


def to_verdict_out(stored: tuple[Verdict, datetime] | None) -> VerdictOut | None:
    if stored is None:
        return None
    verdict, computed_at = stored
    return VerdictOut(
        call=verdict.call, score=verdict.score, parts=verdict.parts, reasons=verdict.reasons, computed_at=computed_at
    )


def _to_setup_out(
    record: SetupRecord, records: list[SetupRecord], verdicts: dict[str, tuple[Verdict, datetime]]
) -> SetupOut:
    # Same rule as the ranking penalty: only an opposite pattern on the same
    # or a higher timeframe counts; a 1m wiggle against a 5m setup doesn't.
    has_conflict = any(
        other.ticker == record.ticker
        and other.direction != record.direction
        and TIMEFRAME_ORDER[other.timeframe] >= TIMEFRAME_ORDER[record.timeframe]
        for other in records
    )
    values = asdict(record)
    # The setup's own `verdict` column is the call at detection; the API shows the
    # stock's current verdict instead.
    for field in ("float_at_detection", "outcome", "resolved_at", "max_favorable_r", "max_adverse_r", "verdict"):
        values.pop(field)
    return SetupOut(**values, has_conflict=has_conflict, verdict=to_verdict_out(verdicts.get(record.ticker)))


def _track_record_summary(stats: PatternStats | None) -> TrackRecordSummaryOut | None:
    if stats is None:
        return None
    return TrackRecordSummaryOut(
        trades=stats.trades,
        win_rate=stats.win_rate,
        average_r=stats.average_r,
        average_win_r=stats.average_win_r,
        tickers=stats.tickers,
        trading_days=stats.trading_days,
        has_enough_history=has_enough_history(stats),
    )


def _setups_response(conn: sqlite3.Connection, ticker: str | None) -> SetupsOut:
    records = list_current_setups(conn, ticker)
    show_shorts = get_show_short_setups(conn)
    verdicts = read_verdicts(conn)
    history: dict[tuple[str, str], PatternStats | None] = {}
    for record in records:
        key = (record.pattern, record.timeframe)
        if key not in history:
            history[key] = stats_for(conn, *key)
    setups = [
        _to_setup_out(record, records, verdicts).model_copy(
            update={"track_record": _track_record_summary(history[(record.pattern, record.timeframe)])}
        )
        for record in records
    ]
    # Shorts are never suggested as trades unless the user turned them on.
    return SetupsOut(
        setups=[setup for setup in setups if setup.direction == "long" or show_shorts],
        warnings=[] if show_shorts else [
            WarningOut(**setup.model_dump(include=set(WarningOut.model_fields)))
            for setup in setups
            if setup.direction == "short"
        ],
        show_short_setups=show_shorts,
    )


@router.get("/setups", response_model=SetupsOut)
def get_setups(conn: DbConnection) -> SetupsOut:
    return _setups_response(conn, None)


@router.get("/stocks/{ticker}/setups", response_model=SetupsOut)
def get_stock_setups(ticker: TickerPath, conn: DbConnection) -> SetupsOut:
    return _setups_response(conn, ticker.upper())


@router.get("/stocks/{ticker}/verdict", response_model=VerdictOut | None)
def get_stock_verdict(ticker: TickerPath, conn: DbConnection) -> VerdictOut | None:
    return to_verdict_out(read_verdicts(conn).get(ticker.upper()))
