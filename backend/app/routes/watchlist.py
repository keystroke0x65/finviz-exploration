import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.config import get_settings
from app.errors import (
    FinvizAuthError,
    FinvizRateLimitError,
    FinvizUnavailableError,
    TickerNotFoundError,
)
from app.finviz_client import ScreenRow, get_quote, run_screen
from app.patterns.verdict import Verdict
from app.routes.dependencies import finviz_error_to_http, get_db_connection
from app.routes.stocks import TickerPath
from app.routes.setups import to_verdict_out
from app.scanning.snapshots import read_snapshots
from app.scanning.verdicts import read_verdicts
from app.schemas import AddTickerIn, FeederResultOut, FeederStatusOut, PinIn, WatchlistEntryOut
from app.watchlist.feeder import run_feeder
from app.watchlist.run_status import FeederResult, get_last_feeder_run
from app.watchlist.store import (
    WatchlistEntry,
    add_manual_entry,
    entry_expires_at,
    list_entries,
    remove_entry,
    set_pinned,
)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]


def _to_entry_out(
    entry: WatchlistEntry,
    snapshots: dict[str, tuple[ScreenRow, datetime]] | None = None,
    verdicts: dict[str, tuple[Verdict, datetime]] | None = None,
) -> WatchlistEntryOut:
    retention_days = get_settings().watchlist_retention_days
    snapshot = (snapshots or {}).get(entry.ticker)
    snapshot_out = None
    if snapshot is not None:
        row, fetched_at = snapshot
        snapshot_out = {
            "price": row.price,
            "change_percent": row.change_percent,
            "after_hours_change_percent": row.after_hours_change_percent,
            "relative_volume": row.relative_volume,
            "fetched_at": fetched_at,
        }
    return WatchlistEntryOut(
        **asdict(entry),
        expires_at=entry_expires_at(entry, retention_days),
        snapshot=snapshot_out,
        verdict=to_verdict_out((verdicts or {}).get(entry.ticker)),
    )


@router.get("", response_model=list[WatchlistEntryOut])
def get_watchlist(conn: DbConnection) -> list[WatchlistEntryOut]:
    snapshots = read_snapshots(conn)
    verdicts = read_verdicts(conn)
    return [_to_entry_out(entry, snapshots, verdicts) for entry in list_entries(conn)]


@router.post("", response_model=WatchlistEntryOut, status_code=201)
def post_watchlist_entry(body: AddTickerIn, conn: DbConnection) -> WatchlistEntryOut:
    ticker = body.ticker.upper()
    try:
        get_quote(ticker)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        raise finviz_error_to_http(exc) from exc
    return _to_entry_out(add_manual_entry(conn, ticker, datetime.now(timezone.utc)))


def _feeder_result_fields(result: FeederResult) -> dict:
    return {
        "screens_run": result.screens_run,
        "tickers_added": result.tickers_added,
        "tickers_updated": result.tickers_updated,
        "tickers_expired": result.tickers_expired,
        "failed_screens": [
            {"screen": name, "reason": reason} for name, reason in result.failed_screens
        ],
    }


@router.post("/refresh", response_model=FeederResultOut)
def post_refresh(conn: DbConnection) -> FeederResultOut:
    result = run_feeder(
        conn, run_screen, datetime.now(timezone.utc), get_settings().watchlist_retention_days
    )
    return FeederResultOut(**_feeder_result_fields(result))


@router.get("/feeder-status", response_model=FeederStatusOut | None)
def get_feeder_status(conn: DbConnection) -> FeederStatusOut | None:
    last_run = get_last_feeder_run(conn)
    if last_run is None:
        return None
    return FeederStatusOut(finished_at=last_run.finished_at, **_feeder_result_fields(last_run.result))


@router.delete("/{ticker}", status_code=204)
def delete_watchlist_entry(ticker: TickerPath, conn: DbConnection) -> Response:
    if not remove_entry(conn, ticker.upper()):
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} is not on the watchlist")
    return Response(status_code=204)


@router.patch("/{ticker}", response_model=WatchlistEntryOut)
def patch_watchlist_entry(ticker: TickerPath, body: PinIn, conn: DbConnection) -> WatchlistEntryOut:
    entry = set_pinned(conn, ticker.upper(), body.is_pinned)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} is not on the watchlist")
    return _to_entry_out(entry)
