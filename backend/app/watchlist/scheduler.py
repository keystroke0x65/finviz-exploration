import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.db import connect
from app.finviz_client import run_screen
from app.scanning.lock import try_scan_lock
from app.scanning.run_status import CompletedScan, CrashedScan, save_scan_attempt
from app.scanning.scanner import ScanDeps, ScanResult, finviz_scan_deps, run_scan
from app.watchlist.run_status import get_last_feeder_run
from app.watchlist.store import expire_stale_entries
from app.watchlist.feeder import FeederResult, RunScreenFunction, is_within_feeder_window, run_feeder

logger = logging.getLogger(__name__)

SECONDS_PER_MINUTE = 60


def run_scheduled_feeder_tick(
    db_path: str, now: datetime, retention_days: int, run_screen_fn: RunScreenFunction
) -> FeederResult | None:
    if not is_within_feeder_window(now):
        return None
    try:
        conn = connect(db_path)
        try:
            result = run_feeder(conn, run_screen_fn, now, retention_days)
        finally:
            conn.close()
    except Exception:
        # The loop is the recovery point: an unexpected failure in one tick is
        # logged with its traceback and the next tick tries again, rather than
        # silently killing the background task for the rest of the session.
        logger.exception("feeder tick failed")
        return None

    logger.info(
        "feeder tick: %d screens, %d added, %d updated, %d expired",
        result.screens_run,
        len(result.tickers_added),
        len(result.tickers_updated),
        len(result.tickers_expired),
    )
    if result.failed_screens:
        # WARNING, not INFO: uvicorn configures only its own loggers, so app
        # INFO lines never print. Reasons never contain the auth token.
        logger.warning(
            "feeder screens failed: %s",
            "; ".join(f"{name}: {reason}" for name, reason in result.failed_screens),
        )
    return result


def run_scheduled_scan(db_path: str, now: datetime, deps: ScanDeps) -> ScanResult | None:
    if not is_within_feeder_window(now):
        return None
    with try_scan_lock() as is_acquired:
        if not is_acquired:
            logger.info("scan skipped: another scan is running")
            return None
        try:
            conn = connect(db_path)
            try:
                result = run_scan(conn, now, deps)
            finally:
                conn.close()
        except Exception as error:
            # Same recovery point as the feeder: log and let the next tick retry,
            # and record it so the Setups view says its list is stale.
            logger.exception("scan failed")
            _record_scan_attempt(db_path, CrashedScan(finished_at=now, error_type=type(error).__name__))
            return None
        _record_scan_attempt(db_path, CompletedScan(finished_at=now, scanned=len(result.scanned), failed=result.failed))

    logger.info("scan: %d tickers scanned, %d setups", len(result.scanned), result.setups_found)
    if result.failed:
        logger.warning("scan failures: %s", "; ".join(f"{ticker}: {reason}" for ticker, reason in result.failed))
    return result


def _record_scan_attempt(db_path: str, attempt: CompletedScan | CrashedScan) -> None:
    conn = connect(db_path)
    try:
        save_scan_attempt(conn, attempt)
    finally:
        conn.close()


def run_scheduled_expiry(db_path: str, now: datetime, retention_days: int) -> list[str]:
    """Expire stale watchlist entries outside the feeder window (evenings, weekends).

    Inside the window the feeder run expires them itself and reports the count in
    its summary; expiring here first would make that summary always say 0.
    """
    if is_within_feeder_window(now):
        return []
    conn = connect(db_path)
    try:
        expired = expire_stale_entries(conn, now, retention_days)
    finally:
        conn.close()
    if expired:
        logger.warning("watchlist expired outside market hours: %s", ", ".join(expired))
    return expired


def seconds_until_first_tick(last_run_at: datetime | None, now: datetime, interval: timedelta) -> float:
    # uvicorn --reload restarts the lifespan on every code change; without this
    # each reload would run a feeder tick and a full scan straight away.
    if last_run_at is None:
        return 0
    # Capped at one interval: if the clock jumped backwards (WSL/Docker drift) a
    # "future" last run must not pause the feeder for hours.
    return min(max((last_run_at + interval - now).total_seconds(), 0), interval.total_seconds())


def _last_feeder_run_at(db_path: str) -> datetime | None:
    # Runs before the loop's own error handling; a bad stored value must not
    # kill the feeder task, so it's treated as "no recent run".
    try:
        conn = connect(db_path)
        try:
            last_run = get_last_feeder_run(conn)
        finally:
            conn.close()
    except Exception:
        logger.exception("could not read the last feeder run; starting the feeder now")
        return None
    return last_run.finished_at if last_run else None


async def feeder_loop(settings: Settings) -> None:
    interval = timedelta(minutes=settings.feeder_interval_minutes)
    delay = seconds_until_first_tick(_last_feeder_run_at(settings.db_path), datetime.now(timezone.utc), interval)
    if delay:
        logger.info("feeder: last run was recent, first tick in %d s", delay)
        await asyncio.sleep(delay)
    while True:
        try:
            await asyncio.to_thread(
                run_scheduled_expiry, settings.db_path, datetime.now(timezone.utc), settings.watchlist_retention_days
            )
        except Exception:
            logger.exception("watchlist expiry failed")
        # Each tick feeds the watchlist first so the scan sees new names.
        feeder_result = await asyncio.to_thread(
            run_scheduled_feeder_tick,
            settings.db_path,
            datetime.now(timezone.utc),
            settings.watchlist_retention_days,
            run_screen,
        )
        if feeder_result is not None:
            await asyncio.to_thread(
                run_scheduled_scan, settings.db_path, datetime.now(timezone.utc), finviz_scan_deps()
            )
        await asyncio.sleep(settings.feeder_interval_minutes * SECONDS_PER_MINUTE)
