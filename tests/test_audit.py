from credibility.audit import COLUMNS, sample


def rows(n):
    st = [{"id": f"X-{i:03d}", "ticker": "X", "quote": "q", "page": "1"} for i in range(n)]
    sc = [{"id": s["id"], "verdict": "met" if i % 2 else "not scorable", "actual_value": "1", "actual_source": "s"}
          for i, s in enumerate(st)]
    return st, sc


def test_sample_is_scored_only_fixed_size_and_reproducible():
    st, sc = rows(300)
    a, b = sample(st, sc), sample(st, sc)
    assert a == b and len(a) == 50 and len({r["id"] for r in a}) == 50
    assert all(r["verdict"] == "met" and list(r) == COLUMNS for r in a)


def test_sample_exports_all_when_fewer_than_fifty_are_scored():
    st, sc = rows(40)
    assert len(sample(st, sc)) == 20
