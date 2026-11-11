from credibility import statements
from credibility.sources import quarter_of
from credibility.transcripts import normalise

PAGES = {3: normalise("Mr. Rao: We expect revenue growth of 15% to 20% in FY24, with EBITDA margin "
                      "of around 7% – 8% for the full year."),
         4: normalise("We will add 20 stores.")}
QUOTE = "We expect revenue growth of 15% to 20% in FY24, with EBITDA margin of around 7% - 8%"


def patch(monkeypatch):
    monkeypatch.setattr(statements, "text_pages", lambda t, q: PAGES)
    monkeypatch.setattr(statements, "calls", lambda study_only=False: {("X", "Q1FY24"): {"call_date": "2023-08-10"}})


def row(**kw):
    base = {"ticker": "X", "call_quarter": "Q1FY24", "page": "3", "speaker": "Rao", "quote": QUOTE,
            "metric": "revenue_growth", "target_value": "15-20%", "target_period": "FY24", "notes": ""}
    base.update(kw)
    return base


def test_normalise_ignores_case_spacing_and_dash_style():
    assert normalise("7%  – 8%\nFor") == normalise("7% - 8% for")
    assert normalise("“quote” it’s") == normalise("\"quote\" it's")


def test_quote_on_cited_page_passes(monkeypatch):
    patch(monkeypatch)
    assert statements.problems([row()]) == []


def test_quote_on_wrong_page_fails(monkeypatch):
    patch(monkeypatch)
    assert any("quote not on" in p for p in statements.problems([row(page="4")]))
    assert any("quote not on" in p for p in statements.problems([row(page="9")]))


def test_paraphrase_fails(monkeypatch):
    patch(monkeypatch)
    bad = statements.problems([row(quote="We expect revenue to grow 15 to 20 percent in FY24 with margin of 7 to 8")])
    assert any("quote not on" in p for p in bad)


def test_length_ellipsis_metric_and_empty_fields(monkeypatch):
    patch(monkeypatch)
    assert any("words" in p for p in statements.problems([row(quote="We will add 20 stores.", page="4")]))
    assert any("ellipsis" in p for p in statements.problems([row(quote=QUOTE + " ...")]))
    assert any("unknown metric" in p for p in statements.problems([row(metric="vibes")]))
    assert any("empty" in p for p in statements.problems([row(target_period="")]))
    assert any("no stored transcript" in p for p in statements.problems([row(call_quarter="Q2FY24")]))


def test_quarter_of_call_month():
    assert quarter_of("Aug 2023") == "Q1FY24"
    assert quarter_of("Nov 2023") == "Q2FY24"
    assert quarter_of("Feb 2024") == "Q3FY24"
    assert quarter_of("May 2024") == "Q4FY24"
