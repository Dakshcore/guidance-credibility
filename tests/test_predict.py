from datetime import date

import numpy as np

from credibility.predict import bootstrap, half_spread, spearman, surprise, window, window_return
from credibility.prices import parse


def test_window_runs_june_to_may_after_the_fiscal_year():
    assert window("FY24") == (date(2024, 6, 1), date(2025, 5, 31))


def test_window_return_uses_first_and_last_day_inside_window():
    s = [(date(2024, 5, 31), 50.0), (date(2024, 6, 3), 100.0), (date(2024, 12, 2), 300.0),
         (date(2025, 5, 30), 120.0), (date(2025, 6, 2), 500.0)]
    assert abs(window_return(s, "FY24") - 0.2) < 1e-12


def test_window_return_is_none_when_an_end_has_no_price():
    late_listing = [(date(2024, 7, 15), 100.0), (date(2025, 5, 30), 120.0)]
    assert window_return(late_listing, "FY24") is None
    assert window_return([], "FY24") is None


def test_surprise_is_profit_change_over_sales():
    a = {("X", "pat:FY24"): 100.0, ("X", "pat:FY25"): 130.0, ("X", "revenue:FY24"): 1000.0}
    assert abs(surprise(a, "X", "FY24") - 0.03) < 1e-12
    assert surprise(a, "X", "FY25") is None


def test_spearman_and_half_spread():
    x = np.array([0.1, 0.2, 0.3, 0.4, 0.1, 0.2, 0.3, 0.4])
    y = np.array([1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0])
    g = np.array(["a"] * 4 + ["b"] * 4)
    assert abs(spearman(x, y) - 1.0) < 1e-12
    assert abs(half_spread(x, y, g) - 2.0) < 1e-12
    assert np.isnan(spearman(np.array([1.0, 1.0, 1.0]), np.array([1.0, 2.0, 3.0])))


def test_bootstrap_is_reproducible_and_brackets_a_perfect_relation():
    x = np.arange(20, dtype=float)
    y = x * 2
    g = np.array(["a"] * 20)
    c = np.array([f"c{i // 2}" for i in range(20)])
    first, second = bootstrap(spearman, x, y, g, c, draws=200), bootstrap(spearman, x, y, g, c, draws=200)
    assert first == second and first[0] > 0.99 and first[2] == 200


def test_parse_drops_days_without_a_price():
    payload = {"chart": {"result": [{"meta": {"gmtoffset": 19800}, "timestamp": [1717213500, 1717299900],
                                     "indicators": {"quote": [{"close": [10.0, None]}],
                                                    "adjclose": [{"adjclose": [9.5, None]}]}}]}}
    assert parse(payload) == [("2024-06-01", 10.0, 9.5)]
