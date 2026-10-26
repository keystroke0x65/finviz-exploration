import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.patterns.ranking import ScoreBreakdown
from app.patterns.trade_plan import TradePlan
from app.patterns.types import PatternMatch, SetupState
from app.setups.resolver import Outcome, Resolution

# Entries are rounded before storing so float noise from different scans
# (2.0 vs 2.00000001) doesn't create duplicate records of the same setup.
ENTRY_DECIMALS = 4

# Scans run every 15 minutes; a ticker whose last scan is older than this
# relative to the newest scan has dropped out of the active set, and its
# setups would be stale on the Setups view.
CURRENT_SCAN_WINDOW = timedelta(minutes=45)


@dataclass(frozen=True)
class SetupRecord:
    id: int
    ticker: str
    pattern: str
    direction: str
    timeframe: str
    entry: float
    stop: float
    capped_target: float
    target_3r: float
    available_reward_risk: float
    risk_percent: float
    blocking_level: float | None
    partial_1r: float
    partial_2r: float
    trailing_stop: float | None
    quality: float
    score: float
    score_parts: dict[str, float]
    key_points: list[tuple[datetime, float]]
    state: SetupState
    # State when first detected: only setups found before their entry was hit
    # are tracked as trades someone could have taken.
    first_state: SetupState
    session: str
    float_at_detection: float | None
    detected_at: datetime
    last_seen_at: datetime
    outcome: Outcome
    resolved_at: datetime | None
    max_favorable_r: float | None
    max_adverse_r: float | None
    # The stock's verdict when the setup was first detected.
    verdict: str | None = None
    # When price last reached the entry; None while forming.
    triggered_at: datetime | None = None


def _optional_time(stored: str | None) -> datetime | None:
    return None if stored is None else datetime.fromisoformat(stored)


def _to_record(row: sqlite3.Row) -> SetupRecord:
    values = dict(row)
    values["score_parts"] = json.loads(row["score_parts"])
    values["key_points"] = [(datetime.fromisoformat(moment), price) for moment, price in json.loads(row["key_points"])]
    values["detected_at"] = datetime.fromisoformat(row["detected_at"])
    values["last_seen_at"] = datetime.fromisoformat(row["last_seen_at"])
    values["resolved_at"] = _optional_time(row["resolved_at"])
    values["triggered_at"] = _optional_time(row["triggered_at"])
    return SetupRecord(**values)


def record_match(
    conn: sqlite3.Connection,
    ticker: str,
    match: PatternMatch,
    plan: TradePlan,
    state: SetupState,
    score: ScoreBreakdown,
    session: str,
    float_millions: float | None,
    now: datetime,
    verdict: str | None = None,
    triggered_at: datetime | None = None,
) -> SetupRecord:
    entry = round(match.entry, ENTRY_DECIMALS)
    key_points = json.dumps([[moment.isoformat(), price] for moment, price in match.key_points])
    # The plan is stored as first detected; later scans only refresh how the
    # setup looks now, so the outcome is judged against the original plan.
    conn.execute(
        """
        INSERT INTO setup_records (
            ticker, pattern, direction, timeframe, entry, stop, capped_target, target_3r,
            available_reward_risk, risk_percent, blocking_level, partial_1r, partial_2r, trailing_stop,
            quality, score, score_parts, key_points, state, first_state, session, float_at_detection,
            detected_at, last_seen_at, verdict, triggered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (ticker, pattern, direction, timeframe, entry) WHERE outcome = 'open' DO UPDATE SET
            score = excluded.score, score_parts = excluded.score_parts, state = excluded.state,
            last_seen_at = excluded.last_seen_at, triggered_at = excluded.triggered_at
        """,
        (
            ticker, match.pattern, match.direction, match.timeframe, entry, match.stop, plan.capped_target,
            plan.target_3r, plan.available_reward_risk, plan.risk_percent, plan.blocking_level, plan.partial_1r,
            plan.partial_2r, plan.trailing_stop, match.quality, score.total, json.dumps(score.parts), key_points,
            state, state, session, float_millions, match.detected_at.isoformat(), now.isoformat(), verdict,
            None if triggered_at is None else triggered_at.isoformat(),
        ),
    )
    conn.commit()
    row = conn.execute(
        """
        SELECT * FROM setup_records
        WHERE ticker = ? AND pattern = ? AND direction = ? AND timeframe = ? AND entry = ?
          AND outcome = 'open'
        """,
        (ticker, match.pattern, match.direction, match.timeframe, entry),
    ).fetchone()
    return _to_record(row)


def mark_ticker_scanned(conn: sqlite3.Connection, ticker: str, now: datetime) -> None:
    conn.execute(
        """
        INSERT INTO ticker_scans (ticker, scanned_at) VALUES (?, ?)
        ON CONFLICT (ticker) DO UPDATE SET scanned_at = excluded.scanned_at
        """,
        (ticker, now.isoformat()),
    )
    conn.commit()


def _recently_scanned_tickers(conn: sqlite3.Connection) -> set[str]:
    scans = [(row["ticker"], datetime.fromisoformat(row["scanned_at"])) for row in conn.execute("SELECT * FROM ticker_scans")]
    if not scans:
        return set()
    newest = max(scanned_at for _, scanned_at in scans)
    return {ticker for ticker, scanned_at in scans if newest - scanned_at <= CURRENT_SCAN_WINDOW}


def list_current_setups(conn: sqlite3.Connection, ticker: str | None = None) -> list[SetupRecord]:
    """Setups seen in each ticker's most recent scan, best score first.

    Without a ticker, only tickers scanned in the latest round count; a stock
    that went quiet days ago shouldn't still show its old setups.
    """
    recent = _recently_scanned_tickers(conn) if ticker is None else None
    rows = conn.execute(
        """
        SELECT setup_records.* FROM setup_records
        JOIN ticker_scans ON ticker_scans.ticker = setup_records.ticker
        WHERE setup_records.last_seen_at = ticker_scans.scanned_at
          AND setup_records.state != 'invalidated'
          AND (? IS NULL OR setup_records.ticker = ?)
        ORDER BY setup_records.score DESC, setup_records.id
        """,
        (ticker, ticker),
    )
    records = [_to_record(row) for row in rows]
    return records if recent is None else [record for record in records if record.ticker in recent]


def list_tickers_with_open_records(conn: sqlite3.Connection) -> list[str]:
    return [row["ticker"] for row in conn.execute("SELECT DISTINCT ticker FROM setup_records WHERE outcome = 'open'")]


def list_open_records(conn: sqlite3.Connection, ticker: str) -> list[SetupRecord]:
    rows = conn.execute("SELECT * FROM setup_records WHERE ticker = ? AND outcome = 'open'", (ticker,))
    return [_to_record(row) for row in rows]


def save_outcome(conn: sqlite3.Connection, record_id: int, resolution: Resolution) -> None:
    conn.execute(
        """
        UPDATE setup_records
        SET outcome = ?, resolved_at = ?, max_favorable_r = ?, max_adverse_r = ?
        WHERE id = ?
        """,
        (
            resolution.outcome,
            None if resolution.resolved_at is None else resolution.resolved_at.isoformat(),
            resolution.max_favorable_r,
            resolution.max_adverse_r,
            record_id,
        ),
    )
    conn.commit()
