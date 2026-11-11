"""Compare the new SENCO verdicts with the existing scorecard in the senco-initiation repo (read only).

`python -m credibility.validate` writes data/senco_validation.csv and prints the agreement rate.

Matching. A new statement is paired with a reference statement from the same call when their quotes overlap
(one contains at least MIN_OVERLAP of the other's words, in order, as a common block) and each side is used
once, best overlap first. Reference rows are limited to the calls in the study period.

Agreement. Verdicts are compared after mapping the reference to this study's rubric (docs/rubric.md
section 7): `no actual` -> `not scorable`. Each disagreement gets a cause from the two sets of scoring inputs:
  rubric: undated      reference `not due` on a statement with no dated period; here `not scorable`
  newly reported       reference `not due` / `no actual`; an actual was found in sources stored here
  not found here       reference scored it; here no actual on the guided basis was found
  different range      both scored, the lo/hi/better used differ
  different actual     both scored on the same range, the actual used differs
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from credibility.score import SCORED, SCORES
from credibility.sources import ROOT, all_quarters
from credibility.statements import STATEMENTS, read
from credibility.transcripts import normalise

REF = ROOT.parent / "senco-initiation" / "data"
OUT = ROOT / "data" / "senco_validation.csv"
MIN_OVERLAP = 0.5
COLUMNS = ["new_id", "ref_id", "call_quarter", "overlap", "new_metric", "ref_metric", "new_target", "ref_target",
           "new_range", "ref_range", "new_actual", "ref_actual", "new_verdict", "ref_verdict", "ref_verdict_mapped",
           "agree", "cause"]
UNDATED = ("medium term", "unspecified", "long term", "ongoing", "not specified", "")


def overlap(a: str, b: str) -> float:
    """Longest common run of words, as a share of the shorter quote."""
    x, y = normalise(a).split(), normalise(b).split()
    if not x or not y:
        return 0.0
    m = SequenceMatcher(None, x, y, autojunk=False).find_longest_match(0, len(x), 0, len(y))
    return m.size / min(len(x), len(y))


def pair(new: list[dict], ref: list[dict]) -> list[tuple[dict, dict, float]]:
    cands = sorted(((overlap(n["quote"], r["quote"]), i, j) for i, n in enumerate(new) for j, r in enumerate(ref)
                    if n["call_quarter"] == r["call_quarter"]), reverse=True)
    used_n, used_r, out = set(), set(), []
    for o, i, j in cands:
        if o < MIN_OVERLAP:
            break
        if i not in used_n and j not in used_r:
            used_n.add(i), used_r.add(j)
            out.append((new[i], ref[j], o))
    return out


def map_ref(v: str) -> str:
    return "not scorable" if v == "no actual" else v


def _f(x: str) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def cause(n: dict, r: dict, ref_period: str) -> str:
    nv, rv = n["verdict"], r["verdict"]
    if rv == "not due" and nv == "not scorable" and ref_period.strip().lower() in UNDATED:
        return "rubric: undated"
    if rv in ("not due", "no actual") and nv in SCORED:
        return "newly reported"
    if rv in SCORED and nv not in SCORED:
        return "not found here"
    if rv in SCORED and nv in SCORED:
        same = (_f(n["lo"]), _f(n["hi"]), n["better"]) == (_f(r["lo"]), _f(r["hi"]), r["better"])
        return "different actual" if same else "different range"
    return "other"


def run() -> tuple[list[dict], dict]:
    period = set(all_quarters())
    guidance = {g["id"]: g for g in read(REF / "guidance.csv")}
    ref = [{**guidance[d["id"]], **d} for d in read(REF / "delivery.csv") if guidance[d["id"]]["call_quarter"] in period]
    scores = {s["id"]: s for s in read(SCORES)}
    new = [{**s, **scores[s["id"]]} for s in read(STATEMENTS) if s["ticker"] == "SENCO"]
    rows = []
    for n, r, o in pair(new, ref):
        mapped = map_ref(r["verdict"])
        agree = n["verdict"] == mapped
        rows.append({"new_id": n["id"], "ref_id": r["id"], "call_quarter": n["call_quarter"], "overlap": f"{o:.2f}",
                     "new_metric": n["metric"], "ref_metric": r["metric"], "new_target": n["target_value"],
                     "ref_target": r["guided_value"], "new_range": f"{n['lo']}..{n['hi']} {n['better']}".strip(),
                     "ref_range": f"{r['lo']}..{r['hi']} {r['better']}".strip(), "new_actual": n["actual_value"],
                     "ref_actual": r["actual"], "new_verdict": n["verdict"], "ref_verdict": r["verdict"],
                     "ref_verdict_mapped": mapped, "agree": "yes" if agree else "no",
                     "cause": "" if agree else cause(n, r, guidance[r["id"]]["target_period"])})
    rows.sort(key=lambda x: x["new_id"])
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    both = [x for x in rows if x["new_verdict"] in SCORED and x["ref_verdict"] in SCORED]
    stats = {"new": len(new), "ref": len(ref), "matched": len(rows),
             "agree": sum(x["agree"] == "yes" for x in rows),
             "both_scored": len(both), "both_scored_agree": sum(x["agree"] == "yes" for x in both),
             "causes": Counter(x["cause"] for x in rows if x["agree"] == "no")}
    return rows, stats


if __name__ == "__main__":
    rows, s = run()
    print(f"new SENCO statements: {s['new']}; reference statements in the same 8 calls: {s['ref']}; "
          f"matched pairs: {s['matched']}")
    if s["matched"]:
        print(f"verdict agreement on matched pairs: {s['agree']} of {s['matched']} ({s['agree'] / s['matched']:.1%})")
    if s["both_scored"]:
        print(f"where both scored beat/met/missed: {s['both_scored_agree']} of {s['both_scored']} "
              f"({s['both_scored_agree'] / s['both_scored']:.1%})")
    print("disagreements by cause:", dict(s["causes"]))
    for x in rows:
        if x["agree"] == "no":
            print(f"  {x['new_id']} vs {x['ref_id']} ({x['call_quarter']}): new {x['new_verdict']} "
                  f"[{x['new_range']}; actual {x['new_actual']}] vs ref {x['ref_verdict']} "
                  f"[{x['ref_range']}; actual {x['ref_actual']}] -> {x['cause']}")
    sys.exit(0)
