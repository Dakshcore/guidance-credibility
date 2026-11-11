"""Apply the reviewer's overrides to the agents' rule files.

data/review_overrides.csv lists statement ids whose agent-drafted rule did not meet the rubric (the actual must
be a reported outcome for the full guided period on the guided basis). `python -m credibility.review` rewrites
those rows in data/scoring_parts/ as `basis none / not scorable` with the reviewer's reason. It only ever
moves a row to not scorable; it never sets or changes a verdict of beat, met or missed.
"""
from __future__ import annotations

import csv

from credibility.sources import ROOT

OVERRIDES = ROOT / "data" / "review_overrides.csv"
PARTS = ROOT / "data" / "scoring_parts"
KEEP = ("id",)


def apply() -> tuple[int, list[str]]:
    with open(OVERRIDES, newline="", encoding="utf-8") as fh:
        wanted = {r["id"]: r["reason"] for r in csv.DictReader(fh)}
    done = set()
    for path in sorted(PARTS.glob("*.csv")):
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            cols, rows = reader.fieldnames, list(reader)
        changed = False
        for r in rows:
            if r["id"] in wanted:
                for c in cols:
                    if c not in KEEP:
                        r[c] = ""
                r.update(basis="none", verdict_override="not scorable", reason="review: " + wanted[r["id"]])
                done.add(r["id"])
                changed = True
        if changed:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
    return len(done), sorted(set(wanted) - done)


if __name__ == "__main__":
    n, missing = apply()
    print(f"overrides applied: {n}; ids not found in any rule file: {', '.join(missing) or 'none'}")
