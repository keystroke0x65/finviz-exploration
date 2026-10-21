import sqlite3
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.routes.dependencies import get_db_connection
from app.schemas import TrackRecordOut
from app.setups.track_record import FloatBucket, compute_track_record

router = APIRouter(prefix="/api/track-record", tags=["track record"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]

# History only starts to move scores once a pattern has this many trades.
MIN_TRADES_FOR_TRACK_RECORD = 30
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
    return TrackRecordOut(rows=[asdict(row) for row in rows], min_trades=MIN_TRADES_FOR_TRACK_RECORD)
