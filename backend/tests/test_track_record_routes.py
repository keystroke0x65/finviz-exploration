from tests.test_track_record import add_record


def test_track_record_route_returns_rows(api_client, db_conn):
    add_record(db_conn, "target", pattern="abcd", timeframe="5m")
    add_record(db_conn, "stop", pattern="abcd", timeframe="5m")

    body = api_client.get("/api/track-record").json()

    assert body["min_trades"] == 30
    [row] = body["rows"]
    assert (row["pattern"], row["timeframe"], row["trades"], row["win_rate"]) == ("abcd", "5m", 2, 0.5)


def test_track_record_route_filters(api_client, db_conn):
    add_record(db_conn, "target", pattern="abcd", timeframe="5m", session="pre-market")
    add_record(db_conn, "target", pattern="bull_flag", timeframe="1m", session="regular")

    rows = api_client.get("/api/track-record?timeframe=1m&session=regular&float_bucket=5m_to_10m").json()["rows"]

    assert [row["pattern"] for row in rows] == ["bull_flag"]


def test_track_record_route_validates_filters(api_client):
    assert api_client.get("/api/track-record?timeframe=2m").status_code == 422
    assert api_client.get("/api/track-record?float_bucket=huge").status_code == 422
    assert api_client.get("/api/track-record?pattern=DROP%20TABLE").status_code == 422
