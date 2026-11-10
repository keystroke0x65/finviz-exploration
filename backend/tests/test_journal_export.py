from app.journal.export import escape_cell


def test_escape_cell_neutralises_formulas():
    assert escape_cell("=SUM(A1)") == "'=SUM(A1)"
    assert escape_cell("+1") == "'+1"
    assert escape_cell("-2") == "'-2"
    assert escape_cell("@cmd") == "'@cmd"


def test_escape_cell_keeps_plain_values():
    assert escape_cell("bull_flag") == "bull_flag"
    assert escape_cell(2.5) == "2.5"
    assert escape_cell(None) == ""


def test_numbers_stay_numbers_even_when_negative():
    assert escape_cell(-50.0) == "-50.0"
    assert escape_cell(-1) == "-1"


def test_entries_are_ordered_by_time_whatever_their_utc_offset():
    from datetime import datetime, timezone

    from app.journal.pass_scoring import PassScore
    from app.journal.store import EMPTY_FACTS, JournalEntry
    from app.journal.summary import ScoredPass
    from app.market_time import EASTERN

    def a_pass(entry_id, decided_at):
        entry = JournalEntry(
            kind="pass", ticker="HOST", direction="long", decided_at=decided_at, setup=None, stock=EMPTY_FACTS,
            plan_stop=None, plan_target=None, fees=0.0, reasons=["low_sykes"], mistakes=[], note="", pass_price=None,
            fills=[], id=entry_id, created_at=decided_at, updated_at=decided_at,
        )
        return ScoredPass(entry, PassScore("not_scored", None))

    earlier_utc = a_pass(1, datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc))  # 10:00 ET
    later_eastern = a_pass(2, datetime(2026, 11, 9, 10, 30, tzinfo=EASTERN))

    from app.journal.export import entries_csv

    lines = entries_csv([], [earlier_utc, later_eastern]).splitlines()

    assert [line.split(",")[0] for line in lines[1:]] == ["2", "1"]
