"""Export a random sample of scored statements for a manual audit.

`python -m credibility.audit` writes data/audit_sample.csv: SAMPLE scored (beat / met / missed) statements,
drawn with a fixed seed so the sample is reproducible. If fewer are scored, all of them are exported.
The last two columns are left empty for the auditor.
"""
from __future__ import annotations

import csv
import random

from credibility.score import SCORED, SCORES
from credibility.sources import ROOT
from credibility.statements import STATEMENTS, read

OUT = ROOT / "data" / "audit_sample.csv"
SAMPLE = 50
SEED = 20261110
COLUMNS = ["id", "ticker", "call_quarter", "call_date", "speaker", "page", "quote", "metric", "target_value",
           "target_period", "lo", "hi", "better", "actual_value", "actual_source", "verdict", "reason",
           "audit_ok", "audit_note"]


def sample(statements: list[dict], scores: list[dict], n: int = SAMPLE, seed: int = SEED) -> list[dict]:
    by_id = {s["id"]: s for s in statements}
    scored = sorted((r for r in scores if r["verdict"] in SCORED), key=lambda r: r["id"])
    picked = scored if len(scored) <= n else random.Random(seed).sample(scored, n)
    rows = [{**by_id[r["id"]], **r, "audit_ok": "", "audit_note": ""} for r in picked]
    return sorted(({c: r.get(c, "") for c in COLUMNS} for r in rows), key=lambda r: r["id"])


if __name__ == "__main__":
    scores = read(SCORES)
    rows = sample(read(STATEMENTS), scores)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    total = sum(r["verdict"] in SCORED for r in scores)
    print(f"audit sample: {len(rows)} of {total} scored statements -> {OUT.relative_to(ROOT)} (seed {SEED})")
