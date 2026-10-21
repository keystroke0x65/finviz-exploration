import sqlite3
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.routes.dependencies import get_db_connection
from app.schemas import TrackRecordOut
from app.setups.track_record import (
    MIN_TRADES_FOR_TRACK_RECORD,
    MIN_TRADING_DAYS_FOR_TRACK_RECORD,
    FloatBucket,
    compute_track_record,
    has_enough_history,
)

router = APIRouter(prefix="/api/track-record", tags=["track record"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]

PATTERN_NAME = r"^[a-z_]{1,40}$"


@router.get("", response_model=TrackRecordOut)
def get_track_record(
    conn: DbConnection,
    pattern: Annotated[str | None, Query(pattern=PATTERN_NAME)] = None,
    timeframe: Literal["1m", "5m", "daily"] | None = None,
    float_bucket: FloatBucket | None = None,
    session: Literal["pre-market", "regular", "after-hours", "daily"] | None = None,
) -> TrackRecordOut:
    rows = compute_track_record(
        conn, pattern=pattern, timeframe=timeframe, float_bucket=float_bucket, session=session
    )
    return TrackRecordOut(
        rows=[{**asdict(row), "has_enough_history": has_enough_history(row)} for row in rows],
        min_trades=MIN_TRADES_FOR_TRACK_RECORD,
        min_trading_days=MIN_TRADING_DAYS_FOR_TRACK_RECORD,
    )
