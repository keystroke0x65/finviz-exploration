from datetime import datetime
from unittest.mock import patch

import pytest

from app.errors import FinvizRateLimitError
from app.finviz_client import ScreenResult, ScreenRow
from app.market_time import EASTERN

LOW_FLOAT_SCREEN = {
    "name": "  Mine  ",
    "form": {"country": "usa", "price_under": 20},
    "extra_filters": ["ta_rsi_os30"],
    "signal": "ta_topgainers",
    "order": "-change",
    "feeds_watchlist": True,
}

HOST_ROW = ScreenRow(
    ticker="HOST", company="Host Digital Inc", country="USA", market_cap_millions=79.8,
    float_millions=5.46, average_volume_thousands=433.04, relative_volume=14.22, price=2.83,
    change_percent=47.4, volume=6158186, after_hours_close=2.73,
    after_hours_change_percent=-3.53, news_time=datetime(2026, 10, 20, 10, 36, 3, tzinfo=EASTERN),
    news_url="https://elite.finviz.com/news/1", news_title="Buyback",
)


@pytest.fixture(autouse=True)
def finviz_recognises_every_code():
    with patch("app.routes.screens.find_unrecognised_codes", return_value=[]) as mock_check:
        yield mock_check


def _create(api_client, body=LOW_FLOAT_SCREEN) -> dict:
    response = api_client.post("/api/screens", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_screen_from_form_stores_codes_and_returns_finviz_url(api_client):
    created = _create(api_client)

    listed = api_client.get("/api/screens").json()
    assert listed == [created]
    assert created["name"] == "Mine"
    assert created["form"]["country"] == "usa"
    assert created["form"]["price_under"] == 20
    assert created["extra_filters"] == ["ta_rsi_os30"]
    assert created["feeds_watchlist"] is True
    assert "f=geo_usa,sh_price_u20,ta_rsi_os30" in created["finviz_url"]
    assert "s=ta_topgainers" in created["finviz_url"]


def test_create_screen_rejects_form_value_not_in_options(api_client):
    body = {**LOW_FLOAT_SCREEN, "form": {"price_under": 17}}

    response = api_client.post("/api/screens", json=body)

    assert response.status_code == 422
    assert "price_under" in response.json()["detail"]


def test_create_screen_rejects_bad_extra_code(api_client):
    body = {**LOW_FLOAT_SCREEN, "extra_filters": ["geo usa; drop"]}

    assert api_client.post("/api/screens", json=body).status_code == 422


def test_create_screen_rejects_blank_name(api_client):
    body = {**LOW_FLOAT_SCREEN, "name": "   "}

    assert api_client.post("/api/screens", json=body).status_code == 422


def test_create_screen_rejects_too_many_extra_codes(api_client):
    body = {**LOW_FLOAT_SCREEN, "extra_filters": [f"code_{n}" for n in range(51)]}

    assert api_client.post("/api/screens", json=body).status_code == 422


def test_update_screen_changes_it(api_client):
    created = _create(api_client)
    body = {**LOW_FLOAT_SCREEN, "name": "Renamed", "form": {}, "extra_filters": [], "feeds_watchlist": False}

    response = api_client.put(f"/api/screens/{created['id']}", json=body)

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    assert response.json()["feeds_watchlist"] is False


def test_update_missing_screen_returns_404(api_client):
    assert api_client.put("/api/screens/999", json=LOW_FLOAT_SCREEN).status_code == 404


def test_delete_screen_then_missing(api_client):
    created = _create(api_client)

    assert api_client.delete(f"/api/screens/{created['id']}").status_code == 204
    assert api_client.delete(f"/api/screens/{created['id']}").status_code == 404


def test_parse_url_returns_draft_with_unknown_codes_as_extra(api_client):
    url = "https://finviz.com/screener.ashx?v=111&f=geo_usa,fa_pe_u10,sh_float_u10&s=ta_topgainers"

    response = api_client.post("/api/screens/parse-url", json={"url": url})

    assert response.status_code == 200
    assert response.json() == {
        "form": {
            "country": "usa", "price_under": None, "float_under_millions": 10,
            "market_cap": None, "volume_over_thousands": None, "relative_volume_over": None,
        },
        "extra_filters": ["fa_pe_u10"],
        "signal": "ta_topgainers",
        "order": None,
        "ignored_params": [],
    }


def test_parse_url_rejects_non_finviz_url(api_client):
    response = api_client.post("/api/screens/parse-url", json={"url": "https://evil.example/x"})

    assert response.status_code == 422


def test_form_fields_lists_options_and_signals(api_client):
    body = api_client.get("/api/screens/form-fields").json()

    assert 20 in body["options"]["price_under"]
    assert body["signals"]["ta_topgainers"] == "Top gainers"


@patch("app.routes.screens.run_screen", return_value=ScreenResult([HOST_ROW]))
def test_run_screen_returns_rows(mock_run_screen, api_client):
    created = _create(api_client)

    response = api_client.post(f"/api/screens/{created['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["rows"][0]["ticker"] == "HOST"
    assert body["rows"][0]["after_hours_change_percent"] == -3.53
    assert body["rows"][0]["news_time"] == "2026-10-20T10:36:03-04:00"
    assert "fetched_at" in body
    mock_run_screen.assert_called_once_with(
        ["geo_usa", "sh_price_u20", "ta_rsi_os30"], "ta_topgainers", "-change"
    )


def test_run_missing_screen_returns_404(api_client):
    assert api_client.post("/api/screens/999/run").status_code == 404


@patch("app.routes.screens.run_screen", side_effect=FinvizRateLimitError("screen"))
def test_run_screen_maps_rate_limit_to_503(mock_run_screen, api_client):
    created = _create(api_client)

    response = api_client.post(f"/api/screens/{created['id']}/run")

    assert response.status_code == 503
    assert "rate limiting" in response.json()["detail"]


def test_create_screen_checks_extra_codes_and_signal_with_finviz(api_client, finviz_recognises_every_code):
    _create(api_client)

    # Form codes are verified by the sanity script, so only pasted extras
    # and the signal cost Finviz requests.
    finviz_recognises_every_code.assert_called_once_with(["ta_rsi_os30"], "ta_topgainers")


def test_create_screen_rejects_codes_finviz_does_not_recognise(api_client, finviz_recognises_every_code):
    finviz_recognises_every_code.return_value = ["sh_flaot_u10"]
    body = {**LOW_FLOAT_SCREEN, "extra_filters": ["sh_flaot_u10"]}

    response = api_client.post("/api/screens", json=body)

    assert response.status_code == 422
    assert "sh_flaot_u10" in response.json()["detail"]
    assert api_client.get("/api/screens").json() == []


def test_update_screen_rejects_codes_finviz_does_not_recognise(api_client, finviz_recognises_every_code):
    created = _create(api_client)
    finviz_recognises_every_code.return_value = ["ta_bogus"]

    response = api_client.put(f"/api/screens/{created['id']}", json={**LOW_FLOAT_SCREEN, "signal": "ta_bogus"})

    assert response.status_code == 422
    assert api_client.get("/api/screens").json()[0]["signal"] == "ta_topgainers"


def test_create_screen_maps_finviz_failure_during_code_check(api_client, finviz_recognises_every_code):
    finviz_recognises_every_code.side_effect = FinvizRateLimitError("check filter codes")

    assert api_client.post("/api/screens", json=LOW_FLOAT_SCREEN).status_code == 503


def test_update_only_checks_new_codes(api_client, finviz_recognises_every_code):
    created = _create(api_client)
    finviz_recognises_every_code.reset_mock()

    api_client.put(f"/api/screens/{created['id']}", json={**LOW_FLOAT_SCREEN, "name": "Renamed"})
    assert finviz_recognises_every_code.call_count == 0  # nothing new: no Finviz requests

    api_client.put(f"/api/screens/{created['id']}",
                   json={**LOW_FLOAT_SCREEN, "extra_filters": ["ta_rsi_os30", "fa_pe_u10"]})
    finviz_recognises_every_code.assert_called_once_with(["fa_pe_u10"], None)


def test_parse_url_reports_unused_url_parts(api_client):
    url = "https://finviz.com/screener.ashx?v=111&f=geo_usa&t=AAPL,MSFT&r=21"

    body = api_client.post("/api/screens/parse-url", json={"url": url}).json()

    assert body["ignored_params"] == ["t", "r"]


WORX_ROW = ScreenRow(**{**HOST_ROW.__dict__, "ticker": "WORX"})


@patch("app.routes.screens.run_screen", return_value=ScreenResult([HOST_ROW, WORX_ROW]))
def test_run_screen_adds_each_stocks_best_setup_and_verdict(mock_run_screen, api_client, db_conn):
    from app.patterns.sliding_scale import SlidingScale
    from app.patterns.verdict import Verdict
    from app.scanning.verdicts import save_verdict
    from tests.test_setups_routes import NOW, store_setup

    store_setup(db_conn, "HOST", pattern="bull_flag", score=70.0, sliding_scale=SlidingScale("C", 8, []))
    store_setup(db_conn, "HOST", pattern="flat_top_breakout", score=85.0, sliding_scale=SlidingScale("B", 10, []))
    save_verdict(db_conn, "HOST", Verdict("leans_long", 0.4, {}, ["Above 5 of 5 trend lines"]), NOW)
    created = _create(api_client)

    rows = {row["ticker"]: row for row in api_client.post(f"/api/screens/{created['id']}/run").json()["rows"]}

    assert rows["HOST"]["top_setup"] == {
        "pattern": "flat_top_breakout", "timeframe": "1m", "score": 85.0,
        "sliding_scale": {"letter": "B", "points": 10, "factors": []},
    }
    assert rows["HOST"]["verdict"]["call"] == "leans_long"
    assert rows["WORX"]["top_setup"] is None
    assert rows["WORX"]["verdict"] is None


@patch("app.routes.screens.run_screen", return_value=ScreenResult([HOST_ROW]))
def test_run_screen_skips_short_setups_while_they_are_hidden(mock_run_screen, api_client, db_conn):
    from tests.test_setups_routes import store_setup

    store_setup(db_conn, "HOST", direction="short", pattern="low_of_day_break")
    created = _create(api_client)

    hidden = api_client.post(f"/api/screens/{created['id']}/run").json()["rows"][0]
    api_client.put("/api/settings", json={"show_short_setups": True})
    shown = api_client.post(f"/api/screens/{created['id']}/run").json()["rows"][0]

    assert hidden["top_setup"] is None
    assert shown["top_setup"]["pattern"] == "low_of_day_break"
