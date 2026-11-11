import pytest

from credibility import score
from credibility.score import point_band, score_row, verdict


@pytest.mark.parametrize("actual,lo,hi,better,want", [
    (17, 15, 20, "higher", "met"),
    (15, 15, 20, "higher", "met"),      # ends are inside
    (20, 15, 20, "higher", "met"),
    (21, 15, 20, "higher", "beat"),
    (14.9, 15, 20, "higher", "missed"),
    (1.3, 1.0, 1.2, "lower", "missed"),  # debt/equity above the guided band
    (0.9, 1.0, 1.2, "lower", "beat"),
    (25, 18, None, "higher", "met"),     # a cleared floor is met, never beat
    (17, 18, None, "higher", "missed"),
    (300, None, 350, "lower", "met"),    # under a ceiling
    (400, None, 350, "lower", "missed"),
    (-1, 0, None, "higher", "missed"),   # direction vs base
])
def test_verdict(actual, lo, hi, better, want):
    assert verdict(actual, lo, hi, better) == want


def test_verdict_rejects_bad_input():
    with pytest.raises(ValueError):
        verdict(1, None, None, "higher")
    with pytest.raises(ValueError):
        verdict(1, 5, 2, "higher")
    with pytest.raises(ValueError):
        verdict(1, 0, 2, "up")


def test_point_band():
    assert point_band(20) == pytest.approx((19, 21))
    assert point_band(7) == pytest.approx((6.65, 7.35))
    lo, hi = point_band(-2)
    assert lo < hi and (lo, hi) == pytest.approx((-2.1, -1.9))


ST = {"id": "X-001", "ticker": "X", "call_quarter": "Q1FY24", "metric": "revenue_growth",
      "target_value": "15-20%", "target_period": "FY24"}


def rule(**kw):
    base = {c: "" for c in score.PART_COLUMNS}
    base.update(id="X-001", **kw)
    return base


def test_screener_row_gets_value_and_named_source():
    row, bad = score_row(ST, rule(lo="15", hi="20", better="higher", basis="screener", screener_key="rev_growth:FY24"),
                         {("X", "rev_growth:FY24"): 28.55}, {}, {})
    assert bad == [] and row["verdict"] == "beat"
    assert row["actual_value"] == "28.55" and "Screener.in" in row["actual_source"]
    assert score.output_problems([row]) == []


def test_missing_screener_key_is_an_error_not_a_verdict():
    row, bad = score_row(ST, rule(lo="15", hi="20", better="higher", basis="screener", screener_key="rev_growth:FY99"),
                         {}, {}, {})
    assert bad and row["verdict"] == "error"


def test_not_scorable_needs_a_reason():
    row, bad = score_row(ST, rule(basis="none", verdict_override="not scorable"), {}, {}, {})
    assert bad and row["verdict"] == "error"
    row, bad = score_row(ST, rule(basis="none", verdict_override="not scorable", reason="no period"), {}, {}, {})
    assert bad == [] and row["verdict"] == "not scorable"


def test_beat_met_missed_cannot_be_set_by_hand():
    for v in ("beat", "met", "missed"):
        row, bad = score_row(ST, rule(basis="none", verdict_override=v, reason="x"), {}, {}, {})
        assert bad and row["verdict"] == "error"
    row, bad = score_row(ST, rule(lo="15", hi="20", better="higher", basis="screener",
                                  screener_key="k", verdict_override="met"), {("X", "k"): 1.0}, {}, {})
    assert bad


def test_call_basis_needs_a_stored_source_quote():
    row, bad = score_row(ST, rule(lo="15", hi="20", better="higher", basis="call", actual_num="18"), {}, {}, {})
    assert bad and row["verdict"] == "error"
    row, bad = score_row(ST, rule(lo="15", hi="20", better="higher", basis="call", actual_num="18",
                                  src_call="Q4FY24", src_page="3", src_quote="we grew 18%"), {}, {}, {})
    assert any("not a stored transcript" in b for b in bad)


def test_missing_rule_is_reported():
    row, bad = score_row(ST, None, {}, {}, {})
    assert bad == ["X-001: no scoring rule"]


def test_output_problems_flags_scored_row_without_source():
    row = {"id": "X-001", "verdict": "met", "actual_value": "18", "actual_source": "", "reason": ""}
    assert score.output_problems([row])
