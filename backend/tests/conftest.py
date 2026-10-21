import pytest

from app import finviz_client


@pytest.fixture(autouse=True)
def skip_finviz_pacing(monkeypatch):
    # The pacer protects the real Finviz account; mocked tests shouldn't wait on it.
    monkeypatch.setattr(finviz_client._request_pacer, "_sleep", lambda seconds: None)


@pytest.fixture
def db_conn(tmp_path):
    from app.db import connect

    conn = connect(str(tmp_path / "test.db"))
    yield conn
    conn.close()


@pytest.fixture
def api_client(db_conn, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app
    from app.routes.dependencies import get_db_connection

    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    get_settings.cache_clear()
    app.dependency_overrides[get_db_connection] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()
