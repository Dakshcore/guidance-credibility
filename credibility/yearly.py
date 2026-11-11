"""Yearly credibility score per company, as fixed in docs/prereg.md.

`python -m credibility.yearly` writes data/credibility_yearly.csv: one row per company and fiscal year with
the counts of beat / met / missed statements resolving in that year, the score and the secondary score
(statements resolving in the year or the year before).
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict

from credibility.score import SCORED, SCORES
from credibility.sources import ROOT
from credibility.statements import read

OUT = ROOT / "data" / "credibility_yearly.csv"
MIN_SCORED = 3
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
COLUMNS = ["ticker", "fy", "beat", "met", "missed", "scored", "score", "scored_2y", "score_2y"]


def resolve_fy(target_period: str) -> int | None:
    """Fiscal year (two digits, e.g. 25 for FY25) in which the target period ends, or None."""
    text = target_period.strip()
    years = re.findall(r"FY\s?(\d{2})\b", text)
    if years:
        return int(years[-1])
    m = re.search(r"\b([A-Za-z]{3})[a-z]*[- ](\d{2})\b", text)
    if m and m.group(1).lower() in MONTHS:
        month, year = MONTHS[m.group(1).lower()], int(m.group(2))
        return year + 1 if month >= 4 else year
    return None


def yearly(scores: list[dict]) -> tuple[list[dict], int]:
    """Rows per (ticker, fy) and the number of scored statements whose period could not be read."""
    counts: dict[tuple[str, int], Counter] = defaultdict(Counter)
    unread = 0
    for r in scores:
        if r["verdict"] not in SCORED:
            continue
        fy = resolve_fy(r["target_period"])
        if fy is None:
            unread += 1
            continue
        counts[(r["ticker"], fy)][r["verdict"]] += 1
    rows = []
    for (t, fy), c in sorted(counts.items()):
        prev = counts.get((t, fy - 1), Counter())
        n = sum(c.values())
        n2 = n + sum(prev.values())
        good2 = c["beat"] + c["met"] + prev["beat"] + prev["met"]
        rows.append({"ticker": t, "fy": f"FY{fy}", "beat": c["beat"], "met": c["met"], "missed": c["missed"],
                     "scored": n, "score": f"{(c['beat'] + c['met']) / n:.4f}",
                     "scored_2y": n2, "score_2y": f"{good2 / n2:.4f}"})
    return rows, unread


if __name__ == "__main__":
    rows, unread = yearly(read(SCORES))
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    ok = sum(r["scored"] >= MIN_SCORED for r in rows)
    text = (f"company-years: {len(rows)}; with >= {MIN_SCORED} scored statements: {ok}; "
            f"scored statements with unreadable period: {unread} -> {OUT.relative_to(ROOT)}")
    (ROOT / "reports" / "yearly_numbers.txt").write_text(text + "\n", encoding="utf-8")
    print(text)
