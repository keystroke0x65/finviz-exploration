from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from app.errors import FinvizUnavailableError
from app.finviz_client import Bar
from app.market_time import EASTERN
from app.patterns.ranking import ScoreBreakdown
from app.setups.store import mark_ticker_scanned, record_match
from tests.test_setup_store import match, plan

DAY = date(2026, 11, 2)
PREVIOUS_DAY = date(2026, 10, 30)
QUOTE = {"Ticker": "HOST", "Company": "Host Corp", "Country": "USA", "Sector": "Technology", "Industry": "Software",
         "Market Cap": "32.36", "Price": "2.4"}


def at(hour, minute=0, day=DAY):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=EASTERN)


def minute_bars():
    return [Bar(at(9, 30) + timedelta(minutes=offset), 2.0, 2.4, 1.95, 2.0 + offset / 100, 10_000) for offset in range(60)]


def fake_bars(ticker, interval):
    if interval == "daily":
        return [Bar(at(0, 0, PREVIOUS_DAY), 1.7, 1.9, 1.6, 1.8, 1_000_000)]
    return minute_bars()


@pytest.fixture(autouse=True)
def finviz():
    with patch("app.routes.journal.get_bars", side_effect=fake_bars) as get_bars, \
            patch("app.routes.journal.get_quote", return_value=QUOTE) as get_quote, \
            patch("app.routes.journal.get_cached_quote", return_value=None), \
            patch("app.routes.journal.set_cached_quote"):
        yield get_bars, get_quote


def iso(moment):
    return moment.isoformat()


def trade_body(**overrides):
    body = {
        "kind": "trade", "ticker": "host", "direction": "long", "setup_record_id": None, "plan_stop": 1.9,
        "plan_target": 2.3, "fees": 0, "mistakes": ["chased"], "note": "",
        "fills": [{"side": "buy", "time": iso(at(9, 45)), "price": 2.0, "shares": 100},
                  {"side": "sell", "time": iso(at(10, 0)), "price": 2.5, "shares": 100}],
    }
    return {**body, **overrides}


def pass_body(**overrides):
    body = {"kind": "pass", "ticker": "HOST", "direction": "long", "setup_record_id": None,
            "reasons": ["low_sykes"], "note": "", "decided_at": iso(at(9, 50))}
    return {**body, **overrides}


def record_setup(conn):
    first_scan, second_scan = at(9, 40), at(9, 55)
    saved = record_match(conn, "HOST", match(), plan(), "forming", ScoreBreakdown(70.0, {}), "regular", 5.0, first_scan)
    record_match(conn, "HOST", match(), plan(), "triggered", ScoreBreakdown(90.0, {}), "regular", 5.0, second_scan)
    mark_ticker_scanned(conn, "HOST", second_scan)
    return saved


def test_reason_catalog(api_client):
    body = api_client.get("/api/journal/reasons").json()

    assert body["pass_reasons"][0]["group"] == "The app's read"
    assert {"key": "low_sykes", "label": "Low Sykes grade"} in body["pass_reasons"][0]["items"]
    assert {"key": "followed_plan", "label": "Followed the plan"} in body["mistakes"]


def test_create_trade_saves_figures_facts_and_bars(api_client, db_conn):
    saved_setup = record_setup(db_conn)

    response = api_client.post("/api/journal/entries", json=trade_body(setup_record_id=saved_setup.id))

    assert response.status_code == 201
    body = response.json()
    assert body["ticker"] == "HOST"
    assert body["figures"]["net_pnl"] == pytest.approx(50.0)
    assert body["figures"]["r_multiple"] == pytest.approx(5.0)
    assert body["setup"]["score"] == 70.0  # as of the 9:45 fill, before the 9:55 rescan
    assert body["setup"]["state"] == "forming"
    assert body["stock"]["price"] == 2.0
    assert body["stock"]["change_percent"] == pytest.approx(11.111, abs=0.01)
    assert body["stock"]["industry"] == "Software"
    assert body["bar_warning"] is None
    assert body["plan_flags"] == ["followed_plan"]
    bars = api_client.get(f"/api/journal/entries/{body['id']}/bars?interval=1m").json()
    assert len(bars["bars"]) == 60
    assert bars["days"] == [{"day": "2026-11-02", "status": "complete"}]


def test_create_trade_while_finviz_is_down_still_saves(api_client, finviz):
    get_bars, _ = finviz
    get_bars.side_effect = FinvizUnavailableError("1m bars HOST", "timeout")

    response = api_client.post("/api/journal/entries", json=trade_body())

    assert response.status_code == 201
    assert response.json()["bar_warning"] == "Chart bars not saved yet, will retry."
    assert response.json()["figures"]["net_pnl"] == pytest.approx(50.0)


def test_create_pass_records_price_at_that_moment(api_client):
    response = api_client.post("/api/journal/entries", json=pass_body())

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "pass"
    assert body["reasons"] == ["low_sykes"]
    assert body["pass_price"] == pytest.approx(2.2)
    assert body["pass_score"]["outcome"] == "not_scored"
    # No setup linked, but what price did next is still tracked: high 2.40 after the 9:50 pass.
    assert body["after_pass"]["best_price"] == pytest.approx(2.4)
    assert body["after_pass"]["best_percent"] == pytest.approx(9.09, abs=0.01)
    assert body["after_pass"]["best_r"] is None


@pytest.mark.parametrize(
    "body, message",
    [
        (trade_body(fills=[{"side": "buy", "time": "2026-11-02T09:45:00-05:00", "price": 2.0, "shares": 100},
                           {"side": "sell", "time": "2026-11-02T09:50:00-05:00", "price": 2.1, "shares": 200}]),
         "would sell more shares than are held"),
        (trade_body(fills=[{"side": "buy", "time": "2099-01-02T09:45:00-05:00", "price": 2.0, "shares": 100}]),
         "in the future"),
        (trade_body(mistakes=["chased", "followed_plan"]), "Followed the plan"),
        (trade_body(plan_stop=2.1), "must be below the first fill"),
        (trade_body(mistakes=["nope"]), "Unknown mistake"),
        (trade_body(setup_record_id=999), "Setup not found"),
        (pass_body(reasons=["nope"]), "Unknown reason"),
        (pass_body(reasons=["other"]), "note"),
        (pass_body(reasons=[]), "at least 1"),
        (trade_body(fills=[{"side": "buy", "time": "2026-11-02T09:45:00", "price": 2.0, "shares": 100}]), "timezone"),
        (trade_body(fills=[{"side": "buy", "time": "2026-11-02T09:45:00-05:00", "price": -1, "shares": 100}]), "greater than 0"),
    ],
)
def test_invalid_entries_are_rejected(api_client, body, message):
    response = api_client.post("/api/journal/entries", json=body)

    assert response.status_code == 422
    assert message in str(response.json()["detail"])


def test_preview_returns_figures_or_the_fill_problem(api_client):
    good = api_client.post("/api/journal/preview", json=trade_body()).json()
    bad = api_client.post(
        "/api/journal/preview",
        json=trade_body(fills=[{"side": "sell", "time": iso(at(9, 45)), "price": 2.0, "shares": 100}]),
    ).json()

    assert good["figures"]["net_pnl"] == pytest.approx(50.0)
    assert good["error"] is None
    assert bad == {"figures": None, "error": "The first fill must be a buy for a long trade."}
    wrong_stop = api_client.post("/api/journal/preview", json=trade_body(plan_stop=2.1)).json()
    assert wrong_stop["error"] == "The plan stop (2.10) must be below the first fill (2.00) for a long trade."


def test_list_get_update_delete(api_client):
    created = api_client.post("/api/journal/entries", json=trade_body()).json()
    api_client.post("/api/journal/entries", json=pass_body())

    assert [entry["kind"] for entry in api_client.get("/api/journal/entries?period=all").json()] == ["pass", "trade"]
    assert len(api_client.get("/api/journal/entries?kind=trade&period=all").json()) == 1

    updated = api_client.put(f"/api/journal/entries/{created['id']}", json=trade_body(note="better entry next time"))
    assert updated.status_code == 200
    assert updated.json()["note"] == "better entry next time"

    assert api_client.delete(f"/api/journal/entries/{created['id']}").status_code == 204
    assert api_client.get(f"/api/journal/entries/{created['id']}").status_code == 404
    assert api_client.put(f"/api/journal/entries/{created['id']}", json=trade_body()).status_code == 404
    assert api_client.delete(f"/api/journal/entries/{created['id']}").status_code == 404


def test_five_minute_bars_are_built_from_saved_minutes(api_client):
    created = api_client.post("/api/journal/entries", json=trade_body()).json()

    bars = api_client.get(f"/api/journal/entries/{created['id']}/bars?interval=5m").json()["bars"]

    assert len(bars) == 12
    assert bars[0]["volume"] == 50_000


def test_day_setups_show_values_at_a_time(api_client, db_conn):
    record_setup(db_conn)

    body = api_client.get(f"/api/journal/setups/HOST?day=2026-11-02&at={iso(at(9, 45)).replace('+', '%2B')}").json()

    assert len(body["matches"]) == 1
    row = body["matches"][0]
    assert (row["pattern"], row["score"], row["state"]) == ("bull_flag", 70.0, "forming")
    assert row["detected_at"] is not None


def test_day_setups_match_the_trade(api_client, db_conn):
    record_setup(db_conn)
    moment = iso(at(9, 45)).replace("+", "%2B")

    shorts = api_client.get(f"/api/journal/setups/HOST?day=2026-11-02&at={moment}&direction=short&price=2.0").json()
    before_detection = iso(datetime(2026, 10, 20, 9, 0, tzinfo=EASTERN)).replace("+", "%2B")
    before = api_client.get(f"/api/journal/setups/HOST?day=2026-11-02&at={before_detection}").json()

    assert (len(shorts["matches"]), len(shorts["others"])) == (0, 1)
    # The sample setup was first detected at 10:00 on Oct 20: not yet there for a 9:00 entry.
    assert (len(before["matches"]), len(before["others"])) == (0, 1)


def test_day_setups_reject_a_bad_direction_or_price(api_client):
    moment = iso(at(9, 45)).replace("+", "%2B")

    assert api_client.get(f"/api/journal/setups/HOST?day=2026-11-02&at={moment}&direction=up").status_code == 422
    assert api_client.get(f"/api/journal/setups/HOST?day=2026-11-02&at={moment}&price=-1").status_code == 422


def test_open_trade_lookup(api_client):
    assert api_client.get("/api/journal/open-trade/HOST").json() is None

    created = api_client.post(
        "/api/journal/entries",
        json=trade_body(fills=[{"side": "buy", "time": iso(at(9, 45)), "price": 2.0, "shares": 100}]),
    ).json()

    assert api_client.get("/api/journal/open-trade/host").json()["id"] == created["id"]


def test_summary_endpoint(api_client):
    api_client.post("/api/journal/entries", json=trade_body())

    body = api_client.get("/api/journal/summary?period=all").json()

    assert body["trades"] == 1
    assert body["net_pnl"] == pytest.approx(50.0)
    assert body["by_mistake"] == [{"label": "chased", "count": 1, "pnl": 50.0}]


def test_daily_loss_levels(api_client):
    assert api_client.get("/api/journal/daily-loss").json()["level"] == "ok"
    now = datetime.now(EASTERN).replace(second=0, microsecond=0) - timedelta(minutes=2)
    api_client.put("/api/settings/journal", json={"risk_per_trade": 50, "max_position": None, "max_daily_loss": 100})
    api_client.post("/api/journal/entries", json=trade_body(fills=[
        {"side": "buy", "time": iso(now - timedelta(minutes=1)), "price": 2.0, "shares": 100},
        {"side": "sell", "time": iso(now), "price": 1.15, "shares": 100},
    ]))

    body = api_client.get("/api/journal/daily-loss").json()

    assert body == {"realised_pnl_today": pytest.approx(-85.0), "max_daily_loss": 100.0, "level": "warning"}


def test_csv_export_escapes_formula_cells(api_client):
    api_client.post("/api/journal/entries", json=trade_body(note="=HYPERLINK(\"x\")"))

    entries = api_client.get("/api/journal/export/entries.csv?period=all")
    fills = api_client.get("/api/journal/export/fills.csv?period=all")

    assert entries.headers["content-type"].startswith("text/csv")
    assert "attachment" in entries.headers["content-disposition"]
    assert "'=HYPERLINK" in entries.text
    assert entries.text.splitlines()[0].startswith("id,kind,ticker")
    assert len(fills.text.strip().splitlines()) == 3


def test_journal_settings_round_trip_and_validation(api_client):
    assert api_client.get("/api/settings/journal").json() == {
        "risk_per_trade": None, "max_position": None, "max_daily_loss": None}

    saved = api_client.put("/api/settings/journal", json={"risk_per_trade": 50, "max_position": 2000, "max_daily_loss": 200})

    assert saved.json() == {"risk_per_trade": 50.0, "max_position": 2000.0, "max_daily_loss": 200.0}
    assert api_client.put("/api/settings/journal", json={"risk_per_trade": -5, "max_position": None,
                                                         "max_daily_loss": None}).status_code == 422


def test_editing_while_finviz_is_down_keeps_the_saved_stock_facts(api_client, finviz):
    created = api_client.post("/api/journal/entries", json=trade_body()).json()
    get_bars, get_quote = finviz
    get_bars.side_effect = FinvizUnavailableError("bars HOST", "timeout")
    get_quote.side_effect = FinvizUnavailableError("quote HOST", "timeout")

    updated = api_client.put(f"/api/journal/entries/{created['id']}", json=trade_body(note="edited")).json()

    assert updated["note"] == "edited"
    assert updated["stock"]["industry"] == "Software"
    assert updated["stock"]["change_percent"] == pytest.approx(created["stock"]["change_percent"])


def test_a_pass_saved_while_finviz_was_down_is_scored_from_its_moment_once_bars_arrive(api_client, db_conn, finviz):
    from app.journal.bars import complete_pending_days

    saved_setup = record_setup(db_conn)
    get_bars, _ = finviz
    get_bars.side_effect = FinvizUnavailableError("bars HOST", "timeout")
    created = api_client.post("/api/journal/entries", json=pass_body(setup_record_id=saved_setup.id)).json()
    assert created["pass_price"] is None

    complete_pending_days(db_conn, at(21, 0), fake_bars)

    # 2.20 at the 9:50 pass was already past the 2.15 target: no trade was left to take.
    assert api_client.get(f"/api/journal/entries/{created['id']}").json()["pass_score"]["outcome"] == "past_target"


def test_entries_can_be_filtered_by_ticker(api_client):
    api_client.post("/api/journal/entries", json=trade_body())
    api_client.post("/api/journal/entries", json=trade_body(ticker="OTHR"))

    rows = api_client.get("/api/journal/entries?kind=trade&period=all&ticker=host").json()

    assert [row["ticker"] for row in rows] == ["HOST"]


def test_daily_loss_needs_only_fills_not_saved_bars(api_client, monkeypatch):
    api_client.post("/api/journal/entries", json=trade_body())

    def no_bars(*args, **kwargs):
        raise AssertionError("daily loss must not read saved bars")

    monkeypatch.setattr("app.journal.service.read_bars", no_bars)

    assert api_client.get("/api/journal/daily-loss").json()["level"] == "ok"
