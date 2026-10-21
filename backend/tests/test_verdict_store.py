from datetime import datetime, timezone

from app.patterns.verdict import Verdict
from app.scanning.verdicts import read_verdicts, save_verdict

NOW = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)


def test_verdict_round_trip(db_conn):
    verdict = Verdict("leans_long", 0.42, {"trend": 1.0, "volume": -0.2}, ["Above 5 of 5 trend lines", "Volume mixed"])

    save_verdict(db_conn, "HOST", verdict, NOW)

    assert read_verdicts(db_conn) == {"HOST": (verdict, NOW)}


def test_saving_again_replaces_the_verdict(db_conn):
    save_verdict(db_conn, "HOST", Verdict("leans_long", 0.4, {}, []), NOW)
    save_verdict(db_conn, "HOST", Verdict("no_clear_edge", 0.1, {}, []), NOW)

    assert read_verdicts(db_conn)["HOST"][0].call == "no_clear_edge"
