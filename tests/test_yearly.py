import pytest

from credibility.yearly import resolve_fy, yearly


@pytest.mark.parametrize("text,fy", [
    ("FY25", 25), ("Q3FY24", 24), ("H2FY23", 23), ("FY24-FY26", 26), ("by Mar-25", 25), ("by Nov-24", 25),
    ("by Apr-24", 25), ("by December 24", 25), ("medium term", None), ("unspecified", None), ("", None),
])
def test_resolve_fy(text, fy):
    assert resolve_fy(text) == fy


def row(ticker, period, verdict):
    return {"ticker": ticker, "target_period": period, "verdict": verdict}


def test_yearly_counts_scores_and_two_year_window():
    scores = [row("X", "FY24", "beat"), row("X", "FY24", "missed"), row("X", "Q2FY25", "met"),
              row("X", "FY25", "not scorable"), row("X", "medium term", "met"), row("Y", "by Mar-25", "missed")]
    rows, unread = yearly(scores)
    assert unread == 1
    by = {(r["ticker"], r["fy"]): r for r in rows}
    assert by[("X", "FY24")]["scored"] == 2 and by[("X", "FY24")]["score"] == "0.5000"
    assert by[("X", "FY25")]["scored"] == 1 and by[("X", "FY25")]["score"] == "1.0000"
    assert by[("X", "FY25")]["scored_2y"] == 3 and by[("X", "FY25")]["score_2y"] == "0.6667"
    assert by[("Y", "FY25")]["score"] == "0.0000"
