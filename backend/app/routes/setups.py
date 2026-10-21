import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from app.routes.dependencies import get_db_connection
from app.routes.stocks import TickerPath
from app.scanning.scanner import finviz_scan_deps, run_scan
from app.patterns.types import TIMEFRAME_ORDER
from app.schemas import ScanIn, ScanOut, SetupOut, SetupsOut
from app.setups.store import SetupRecord, list_current_setups
from app.user_settings import get_show_short_setups

router = APIRouter(prefix="/api", tags=["setups"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]


@router.post("/scans", response_model=ScanOut)
def post_scan(body: ScanIn, conn: DbConnection) -> ScanOut:
    # Runs synchronously: a full watchlist scan of up to 40 active tickers
    # takes about two minutes at Finviz's one-request-per-second pacing.
    tickers = [body.ticker.upper()] if body.ticker else None
    result = run_scan(conn, datetime.now(timezone.utc), finviz_scan_deps(), tickers=tickers)
    return ScanOut(
        scanned=result.scanned,
        failed=[{"ticker": ticker, "reason": reason} for ticker, reason in result.failed],
        setups_found=result.setups_found,
        scanned_at=result.scanned_at,
    )


def _to_setup_out(record: SetupRecord, records: list[SetupRecord]) -> SetupOut:
    # Same rule as the ranking penalty: only an opposite pattern on the same
    # or a higher timeframe counts; a 1m wiggle against a 5m setup doesn't.
    has_conflict = any(
        other.ticker == record.ticker
        and other.direction != record.direction
        and TIMEFRAME_ORDER[other.timeframe] >= TIMEFRAME_ORDER[record.timeframe]
        for other in records
    )
    values = asdict(record)
    for field in ("float_at_detection", "outcome", "resolved_at", "max_favorable_r", "max_adverse_r"):
        values.pop(field)
    return SetupOut(**values, has_conflict=has_conflict)


def _setups_response(conn: sqlite3.Connection, ticker: str | None) -> SetupsOut:
    records = list_current_setups(conn, ticker)
    show_shorts = get_show_short_setups(conn)
    setups = [_to_setup_out(record, records) for record in records]
    # Shorts are never suggested as trades unless the user turned them on.
    return SetupsOut(
        setups=[setup for setup in setups if setup.direction == "long" or show_shorts],
        warnings=[] if show_shorts else [setup for setup in setups if setup.direction == "short"],
        show_short_setups=show_shorts,
    )


@router.get("/setups", response_model=SetupsOut)
def get_setups(conn: DbConnection) -> SetupsOut:
    return _setups_response(conn, None)


@router.get("/stocks/{ticker}/setups", response_model=SetupsOut)
def get_stock_setups(ticker: TickerPath, conn: DbConnection) -> SetupsOut:
    return _setups_response(conn, ticker.upper())
