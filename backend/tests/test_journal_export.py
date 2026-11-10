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
