import pytest

from app import finviz_client


@pytest.fixture(autouse=True)
def skip_finviz_pacing(monkeypatch):
    # The pacer protects the real Finviz account; mocked tests shouldn't wait on it.
    monkeypatch.setattr(finviz_client._request_pacer, "_sleep", lambda seconds: None)
