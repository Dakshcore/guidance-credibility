"""Score each statement against what was later reported (rubric: docs/rubric.md).

Inputs
- data/statements.csv: the statements (from credibility.statements).
- data/scoring_parts/<TICKER>.csv: one row per statement id with the guided range as numbers, which way is
  better, and where the actual comes from:
    basis = screener  -> `screener_key` in data/actuals_screener.csv
    basis = call      -> `actual_num` stated by management on a later stored call, with `src_call`,
                         `src_page` and a verbatim `src_quote` (optionally a second source in `src2_*`)
    basis = none      -> `verdict_override` is "not scorable" or "not due", with the reason in `reason`
- data/actuals_screener.csv (from credibility.actuals).

`python -m credibility.score` checks the inputs, writes data/scores.csv and prints the counts.
`python -m credibility.score check [part.csv ...]` only checks (use on a single part while building it).

Only "not scorable" and "not due" can be set by hand. beat / met / missed always come from `verdict()`.
"""
from __future__ import annotations

import csv
import math
import sys
from collections import Counter
from pathlib import Path

from credibility import actuals as act
from credibility.sources import ROOT
from credibility.statements import STATEMENTS, calls, quote_on_page, read

PARTS = ROOT / "data" / "scoring_parts"
SCORES = ROOT / "data" / "scores.csv"
PART_COLUMNS = ["id", "lo", "hi", "better", "basis", "screener_key", "actual_num", "actual_text", "src_call",
                "src_page", "src_quote", "src2_call", "src2_page", "src2_quote", "verdict_override", "reason"]
COLUMNS = ["id", "ticker", "call_quarter", "metric", "target_value", "target_period", "lo", "hi", "better",
           "basis", "actual_value", "actual_source", "verdict", "reason"]
POINT_BAND = 0.05  # "~x" is scored as x +/- 5% of x
SCORED = ("beat", "met", "missed")
UNSCORED = ("not scorable", "not due")


def point_band(point: float, band: float = POINT_BAND) -> tuple[float, float]:
    """The range used for a point guide: 20 -> (19, 21); -2 -> (-2.1, -1.9)."""
    a, b = point * (1 - band), point * (1 + band)
    return (min(a, b), max(a, b))


def verdict(actual: float, lo: float | None, hi: float | None, better: str) -> str:
    """met inside [lo, hi]; outside, beat if on the better side, else missed. An open end is None."""
    if better not in ("higher", "lower"):
        raise ValueError(f"better must be 'higher' or 'lower', got {better!r}")
    if lo is None and hi is None:
        raise ValueError("a range needs at least one end")
    lo = -math.inf if lo is None else lo
    hi = math.inf if hi is None else hi
    if lo > hi:
        raise ValueError(f"lo {lo} is above hi {hi}")
    if lo <= actual <= hi:
        return "met"
    return "beat" if (actual > hi) == (better == "higher") else "missed"


def _num(s: str | None) -> float | None:
    s = (s or "").strip().replace(",", "")
    return float(s) if s else None


def read_rules(paths: list[Path] | None = None) -> dict[str, dict]:
    out = {}
    for p in paths or sorted(PARTS.glob("*.csv")):
        for r in read(p):
            out[r["id"]] = r
    return out


def score_row(st: dict, rule: dict | None, screener: dict[tuple[str, str], float], cache: dict,
              known: dict) -> tuple[dict, list[str]]:
    """One output row plus any problems. A row with problems gets verdict 'error'."""
    row = {c: st.get(c, "") for c in ("id", "ticker", "call_quarter", "metric", "target_value", "target_period")}
    row.update(lo="", hi="", better="", basis="", actual_value="", actual_source="", verdict="error", reason="")
    sid, bad = st["id"], []
    if rule is None:
        return row, [f"{sid}: no scoring rule"]
    row.update(lo=rule["lo"], hi=rule["hi"], better=rule["better"], basis=rule["basis"], reason=rule["reason"])
    basis, override = rule["basis"], rule["verdict_override"]
    if basis == "none":
        if override not in UNSCORED:
            bad.append(f"{sid}: basis none needs verdict_override 'not scorable' or 'not due'")
        elif not rule["reason"].strip():
            bad.append(f"{sid}: {override} without a reason")
        else:
            row["verdict"] = override
        return row, bad
    if override:
        bad.append(f"{sid}: verdict_override is only allowed with basis none")
    if basis == "screener":
        key = (st["ticker"], rule["screener_key"])
        if key not in screener:
            bad.append(f"{sid}: screener key {rule['screener_key']!r} not in actuals_screener.csv")
        else:
            actual = screener[key]
            row.update(actual_value=f"{actual:g}",
                       actual_source=f"Screener.in consolidated page ({rule['screener_key']}), "
                                     f"data/raw/screener/{st['ticker']}.html")
    elif basis == "call":
        actual = _num(rule["actual_num"])
        if actual is None:
            bad.append(f"{sid}: basis call needs actual_num")
        srcs = []
        for pre in ("src", "src2"):
            call, page, quote = rule.get(f"{pre}_call", ""), rule.get(f"{pre}_page", ""), rule.get(f"{pre}_quote", "")
            if not (call or quote):
                continue
            if (st["ticker"], call) not in known:
                bad.append(f"{sid}: actual source call {call!r} is not a stored transcript")
            elif not quote_on_page(st["ticker"], call, page, quote, cache):
                bad.append(f"{sid}: actual quote not on {call} page {page}")
            else:
                srcs.append(f"{call} call p{page}")
        if not srcs and not any(b.startswith(sid) for b in bad):
            bad.append(f"{sid}: basis call needs a source call, page and quote")
        if actual is not None:
            row.update(actual_value=rule["actual_text"].strip() or f"{actual:g}",
                       actual_source="; ".join(srcs))
    else:
        bad.append(f"{sid}: unknown basis {basis!r}")
    if bad:
        return row, bad
    try:
        row["verdict"] = verdict(actual, _num(rule["lo"]), _num(rule["hi"]), rule["better"])
    except ValueError as e:
        bad.append(f"{sid}: {e}")
    return row, bad


def score(rule_paths: list[Path] | None = None) -> tuple[list[dict], list[str]]:
    statements = read(STATEMENTS)
    rules = read_rules(rule_paths)
    if rule_paths:  # checking single parts: only the statements they cover
        statements = [s for s in statements if s["id"] in rules]
    screener, cache, known = act.load(), {}, calls()
    rows, problems = [], [f"{i}: rule for an unknown statement id" for i in rules
                          if i not in {s["id"] for s in read(STATEMENTS)}]
    for st in statements:
        row, bad = score_row(st, rules.get(st["id"]), screener, cache, known)
        rows.append(row)
        problems += bad
    return rows, problems


def output_problems(rows: list[dict]) -> list[str]:
    """The target-state checks on the finished file: scored rows have an actual and a named source."""
    out = []
    for r in rows:
        if r["verdict"] in SCORED and not (r["actual_value"].strip() and r["actual_source"].strip()):
            out.append(f"{r['id']}: scored without an actual value and source")
        if r["verdict"] in UNSCORED and not r["reason"].strip():
            out.append(f"{r['id']}: {r['verdict']} without a reason")
        if r["verdict"] not in SCORED + UNSCORED:
            out.append(f"{r['id']}: verdict {r['verdict']!r}")
    return out


def summary(rows: list[dict]) -> str:
    lines = []
    for t in sorted({r["ticker"] for r in rows}):
        mine = [r for r in rows if r["ticker"] == t]
        c = Counter(r["verdict"] for r in mine)
        n = sum(c[v] for v in SCORED)
        rate = f"{(c['beat'] + c['met']) / n:.1%}" if n else "n/a"
        lines.append(f"{t}: {len(mine)} statements; scored {n} ({n / len(mine):.1%}); "
                     f"beat {c['beat']}, met {c['met']}, missed {c['missed']}, not scorable {c['not scorable']}, "
                     f"not due {c['not due']}; delivered {rate}")
    c = Counter(r["verdict"] for r in rows)
    n = sum(c[v] for v in SCORED)
    lines.append(f"ALL: {len(rows)} statements; scored {n} ({n / len(rows):.1%}); delivered "
                 f"{(c['beat'] + c['met']) / n:.1%}" if n else f"ALL: {len(rows)} statements; none scored")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    check_only = argv[:1] == ["check"]
    paths = [Path(a) for a in argv[1:]] if check_only and argv[1:] else None
    rows, problems = score(paths)
    problems += [] if problems else output_problems(rows)
    if problems:
        print("\n".join(problems))
        print(f"{len(problems)} problems; data/scores.csv not written")
        return 1
    if not check_only:
        with open(SCORES, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
    print(summary(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
