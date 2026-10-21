import logging
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import connect
from app.finviz_client import ScreenResult
from app.main import app
from app.screens.store import list_screens, seed_default_screens
from app.watchlist.feeder import FeederResult
from app.watchlist.scheduler import run_scheduled_feeder_tick

TUESDAY_10AM_ET = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
SATURDAY_10AM_ET = datetime(2026, 10, 24, 14, 0, tzinfo=timezone.utc)
RETENTION_DAYS = 90


def _seeded_db_path(tmp_path) -> str:
    db_path = str(tmp_path / "feeder.db")
    conn = connect(db_path)
    seed_default_screens(conn, TUESDAY_10AM_ET)
    conn.close()
    return db_path


def test_scheduler_tick_skips_outside_window(tmp_path):
    calls = []

    result = run_scheduled_feeder_tick(
        _seeded_db_path(tmp_path), SATURDAY_10AM_ET, RETENTION_DAYS,
        lambda *args: calls.append(args),
    )

    assert result is None
    assert calls == []


def test_scheduler_tick_runs_feeder_inside_window(tmp_path):
    result = run_scheduled_feeder_tick(
        _seeded_db_path(tmp_path), TUESDAY_10AM_ET, RETENTION_DAYS,
        lambda *args: ScreenResult([]),
    )

    assert isinstance(result, FeederResult)
    assert result.screens_run == 1


def test_scheduler_tick_survives_feeder_exception(tmp_path, caplog):
    def broken_run_screen(*args):
        raise RuntimeError("unexpected parser crash")

    with caplog.at_level(logging.ERROR):
        result = run_scheduled_feeder_tick(
            _seeded_db_path(tmp_path), TUESDAY_10AM_ET, RETENTION_DAYS, broken_run_screen
        )

    assert result is None
    assert "feeder tick failed" in caplog.text


def test_settings_read_feeder_env(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    monkeypatch.setenv("FEEDER_INTERVAL_MINUTES", "5")
    monkeypatch.setenv("WATCHLIST_RETENTION_DAYS", "30")
    monkeypatch.setenv("IS_FEEDER_ENABLED", "false")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.feeder_interval_minutes == 5
    assert settings.watchlist_retention_days == 30
    assert settings.is_feeder_enabled is False
    get_settings.cache_clear()


def test_settings_feeder_defaults(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    for name in ("FEEDER_INTERVAL_MINUTES", "WATCHLIST_RETENTION_DAYS", "IS_FEEDER_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.feeder_interval_minutes == 15
    assert settings.watchlist_retention_days == 90
    assert settings.is_feeder_enabled is True
    get_settings.cache_clear()


def test_lifespan_seeds_default_screens(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("IS_FEEDER_ENABLED", "false")
    get_settings.cache_clear()

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    conn = connect(str(db_path))
    assert len(list_screens(conn)) == 2
    conn.close()
    get_settings.cache_clear()


def test_scheduler_tick_logs_failed_screens_as_warning(tmp_path, caplog):
    from app.errors import FinvizAuthError

    def rejected_token(*args):
        raise FinvizAuthError()

    with caplog.at_level(logging.WARNING, logger="app.watchlist.scheduler"):
        run_scheduled_feeder_tick(_seeded_db_path(tmp_path), TUESDAY_10AM_ET, RETENTION_DAYS, rejected_token)

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "Top gainers — low float" in warnings[0].getMessage()
    assert "rejected the configured auth token" in warnings[0].getMessage()
