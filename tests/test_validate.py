from credibility.validate import cause, map_ref, overlap, pair


def test_overlap_of_a_trimmed_quote_is_full():
    a = "we expect revenue growth of 15% to 20% in FY24 with stable margins"
    assert overlap(a, "revenue growth of 15% to 20% in FY24") == 1.0
    assert overlap(a, "we will open twenty showrooms next year in the east") < 0.3


def test_pair_uses_each_row_once_and_only_within_a_call():
    new = [{"call_quarter": "Q1FY24", "quote": "we will add twenty stores this year across regions"},
           {"call_quarter": "Q2FY24", "quote": "we will add twenty stores this year across regions"}]
    ref = [{"call_quarter": "Q1FY24", "quote": "add twenty stores this year across regions"}]
    out = pair(new, ref)
    assert len(out) == 1 and out[0][0] is new[0]


def test_reference_no_actual_maps_to_not_scorable():
    assert map_ref("no actual") == "not scorable" and map_ref("beat") == "beat"


def test_causes():
    n = {"verdict": "not scorable", "lo": "", "hi": "", "better": ""}
    assert cause(n, {"verdict": "not due"}, "medium term") == "rubric: undated"
    n = {"verdict": "met", "lo": "15", "hi": "20", "better": "higher"}
    assert cause(n, {"verdict": "not due"}, "FY26") == "newly reported"
    assert cause(n, {"verdict": "beat", "lo": "15.0", "hi": "20", "better": "higher"}, "FY24") == "different actual"
    assert cause(n, {"verdict": "beat", "lo": "15", "hi": "18", "better": "higher"}, "FY24") == "different range"
    assert cause({"verdict": "not scorable"}, {"verdict": "beat"}, "FY24") == "not found here"
