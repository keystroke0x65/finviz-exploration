"""How each pattern has actually played out on the user's stocks.

Only trades someone could have taken count: setups that hit their target or stop, or
expired after their entry filled. Setups that never filled, were first seen past entry
(not_tracked), lost their bars (unresolved) or are still open are counted separately.

R per trade: a target hit earns the plan's available reward:risk, a stop loses 1R, and
an expiry after filling counts as 0R because the exit price isn't recorded.
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

FloatBucket = Literal["under_5m", "5m_to_10m", "10m_to_20m", "20m_to_50m", "over_50m", "unknown"]

FLOAT_BUCKETS: list[tuple[float, FloatBucket]] = [
    (5.0, "under_5m"),
    (10.0, "5m_to_10m"),
    (20.0, "10m_to_20m"),
    (50.0, "20m_to_50m"),
]
NOT_A_TRADE = {"not_tracked", "unresolved"}
# History only starts to move scores once a pattern has this many trades.
MIN_TRADES_FOR_TRACK_RECORD = 30


def classify_float(float_millions: float | None) -> FloatBucket:
    if float_millions is None:
        return "unknown"
    for upper_bound, bucket in FLOAT_BUCKETS:
        if float_millions < upper_bound:
            return bucket
    return "over_50m"


@dataclass(frozen=True)
class PatternStats:
    pattern: str
    timeframe: str
    trades: int
    wins: int
    losses: int
    expired_after_fill: int
    win_rate: float | None
    average_r: float | None
    average_max_favorable_r: float | None
    not_trades: int
    still_open: int


def _trade_r(row: sqlite3.Row) -> float | None:
    """R earned by a trade, or None when the record isn't a trade."""
    if row["outcome"] == "target":
        return row["available_reward_risk"]
    if row["outcome"] == "stop":
        return -1.0
    if row["outcome"] == "expired" and row["max_favorable_r"] is not None:
        return 0.0
    return None


def _summarise(pattern: str, timeframe: str, rows: list[sqlite3.Row]) -> PatternStats:
    trade_rows = [row for row in rows if _trade_r(row) is not None]
    trade_rs = [_trade_r(row) for row in trade_rows]
    excursions = [row["max_favorable_r"] for row in trade_rows if row["max_favorable_r"] is not None]
    wins = sum(1 for row in trade_rows if row["outcome"] == "target")
    trades = len(trade_rows)
    return PatternStats(
        pattern=pattern,
        timeframe=timeframe,
        trades=trades,
        wins=wins,
        losses=sum(1 for row in trade_rows if row["outcome"] == "stop"),
        expired_after_fill=sum(1 for row in trade_rows if row["outcome"] == "expired"),
        win_rate=wins / trades if trades else None,
        average_r=sum(trade_rs) / trades if trades else None,
        average_max_favorable_r=sum(excursions) / len(excursions) if excursions else None,
        not_trades=sum(
            1 for row in rows
            if row["outcome"] in NOT_A_TRADE or (row["outcome"] == "expired" and row["max_favorable_r"] is None)
        ),
        still_open=sum(1 for row in rows if row["outcome"] == "open"),
    )


def compute_track_record(
    conn: sqlite3.Connection,
    *,
    pattern: str | None = None,
    timeframe: str | None = None,
    float_bucket: FloatBucket | None = None,
    session: str | None = None,
) -> list[PatternStats]:
    rows = conn.execute(
        """
        SELECT pattern, timeframe, outcome, available_reward_risk, max_favorable_r, float_at_detection
        FROM setup_records
        WHERE (? IS NULL OR pattern = ?) AND (? IS NULL OR timeframe = ?) AND (? IS NULL OR session = ?)
        """,
        (pattern, pattern, timeframe, timeframe, session, session),
    ).fetchall()
    groups: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        if float_bucket is not None and classify_float(row["float_at_detection"]) != float_bucket:
            continue
        groups[(row["pattern"], row["timeframe"])].append(row)
    stats = [_summarise(key[0], key[1], group) for key, group in groups.items()]
    return sorted(stats, key=lambda item: (-item.trades, item.pattern, item.timeframe))


def stats_for(conn: sqlite3.Connection, pattern: str, timeframe: str) -> PatternStats | None:
    rows = compute_track_record(conn, pattern=pattern, timeframe=timeframe)
    return rows[0] if rows else None
