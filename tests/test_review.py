import csv

from credibility import review


def test_override_moves_a_row_to_not_scorable_and_leaves_others_alone(tmp_path, monkeypatch):
    parts = tmp_path / "parts"
    parts.mkdir()
    cols = ["id", "basis", "lo", "hi", "better", "actual_value", "verdict_override", "reason"]
    rows = [dict(zip(cols, ["X-001", "call", "10", "12", "higher", "13", "", "full year"])),
            dict(zip(cols, ["X-002", "call", "5", "6", "higher", "4", "", "full year"]))]
    with open(parts / "X_A.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    over = tmp_path / "overrides.csv"
    over.write_text("id,reason\nX-001,part-period actual\nX-999,not there\n", encoding="utf-8")
    monkeypatch.setattr(review, "PARTS", parts)
    monkeypatch.setattr(review, "OVERRIDES", over)

    done, missing = review.apply()

    with open(parts / "X_A.csv", newline="", encoding="utf-8") as fh:
        got = {r["id"]: r for r in csv.DictReader(fh)}
    assert (done, missing) == (1, ["X-999"])
    assert got["X-001"]["basis"] == "none" and got["X-001"]["verdict_override"] == "not scorable"
    assert got["X-001"]["lo"] == "" and got["X-001"]["reason"] == "review: part-period actual"
    assert got["X-002"] == rows[1]
