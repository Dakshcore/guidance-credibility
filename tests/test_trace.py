from credibility.trace import numbers, untraced


def test_numbers_skip_labels_and_dates_and_normalise():
    text = "On 2026-11-11, FY24 and Q1 calls (p7): 1,107 scored, rho -0.030 [-0.342, +0.260], 15.9%, 12-month."
    assert numbers(text) == ["1107", "-0.030", "-0.342", "0.260", "15.9%", "12"]


def test_untraced_flags_a_number_with_no_source():
    assert untraced("n=57 and 58", ["test n=57 companies=34"]) == ["58"]
    assert untraced("Spearman -0.030", ["Spearman +0.030"]) == ["-0.030"]
