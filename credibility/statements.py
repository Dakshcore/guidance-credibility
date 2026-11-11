"""Merge the per-company statement extracts into data/statements.csv and check every quote against its page.

`python -m credibility.statements merge` combines data/statements_parts/<TICKER>_*.csv, orders rows by
ticker, call and page, and numbers them TICKER-001, TICKER-002, ...
`python -m credibility.statements check [part.csv ...]` checks data/statements.csv, or the given part files.

A row fails when: the call is not in data/sources.csv, the quote is not on the cited page of the stored
transcript, the quote is not 10-45 words, it contains an ellipsis, the metric is not in the rubric list, or a
required field is empty.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

from credibility.sources import ROOT, read_sources
from credibility.transcripts import normalise, text_pages

STATEMENTS = ROOT / "data" / "statements.csv"
PARTS = ROOT / "data" / "statements_parts"
PART_COLUMNS = ["call_quarter", "page", "speaker", "quote", "metric", "target_value", "target_period", "notes"]
COLUMNS = ["id", "ticker", "call_quarter", "call_date", "speaker", "quote", "page", "metric", "target_value",
           "target_period", "notes"]
REQUIRED = ["call_quarter", "page", "speaker", "quote", "metric", "target_value", "target_period"]
METRICS = {"revenue_growth", "revenue", "sssg", "gross_margin", "ebitda_margin", "ebit_margin", "pat_margin",
           "ebitda_growth", "pat_growth", "pat", "store_additions", "store_count", "capex", "debt", "inventory",
           "working_capital", "tax_rate", "mix", "costs", "other"}
MIN_WORDS, MAX_WORDS = 10, 45


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def calls(study_only: bool = False) -> dict[tuple[str, str], dict]:
    """Stored transcripts. Calls after the study period (role 'actuals') can back an actual, not a statement."""
    return {(r["ticker"], r["quarter"]): r for r in read_sources()
            if r["status"] == "ok" and not (study_only and (r.get("role") or "study") != "study")}


def quote_on_page(ticker: str, quarter: str, page: str, quote: str, cache: dict | None = None) -> bool:
    cache = {} if cache is None else cache
    pages = cache.setdefault((ticker, quarter), text_pages(ticker, quarter))
    try:
        text = pages.get(int(page), "")
    except ValueError:
        return False
    return bool(quote.strip()) and normalise(quote) in text


def problems(rows: list[dict]) -> list[str]:
    """Every reason a row fails. Rows need 'ticker'; 'id' is used for the label if present."""
    known, cache, out = calls(study_only=True), {}, []
    for n, r in enumerate(rows, start=2):
        label = r.get("id") or f"{r.get('ticker', '?')} line {n}"
        missing = [c for c in REQUIRED if not (r.get(c) or "").strip()]
        if missing:
            out.append(f"{label}: empty {', '.join(missing)}")
            continue
        if (r["ticker"], r["call_quarter"]) not in known:
            out.append(f"{label}: no stored transcript for {r['ticker']} {r['call_quarter']}")
            continue
        if not quote_on_page(r["ticker"], r["call_quarter"], r["page"], r["quote"], cache):
            out.append(f"{label}: quote not on {r['call_quarter']} page {r['page']}")
        words = len(r["quote"].split())
        if not MIN_WORDS <= words <= MAX_WORDS:
            out.append(f"{label}: quote is {words} words")
        if "..." in r["quote"] or "…" in r["quote"]:
            out.append(f"{label}: quote contains an ellipsis")
        if r["metric"] not in METRICS:
            out.append(f"{label}: unknown metric {r['metric']}")
    return out


def ticker_of(part: Path) -> str:
    return part.stem.split("_")[0]


def read_parts(paths: list[Path] | None = None) -> list[dict]:
    rows = []
    for part in paths or sorted(PARTS.glob("*.csv")):
        for r in read(part):
            rows.append({**r, "ticker": ticker_of(part)})
    return rows


def merge() -> list[dict]:
    known = calls(study_only=True)
    order = {q: i for i, q in enumerate(sorted({q for _, q in known}, key=lambda q: (int(q[4:]), q)))}
    rows = [r for r in read_parts() if (r["ticker"], r["call_quarter"]) in known]
    rows.sort(key=lambda r: (r["ticker"], order[r["call_quarter"]], int(r["page"])))
    seen, kept = set(), []
    for r in rows:  # one row per target per call (rubric section 1): keep the earliest page
        key = (r["ticker"], r["call_quarter"], r["metric"], " ".join(r["target_value"].lower().split()),
               r["target_period"].strip().lower())
        if key not in seen:
            seen.add(key)
            kept.append(r)
    if len(kept) != len(rows):
        print(f"dropped {len(rows) - len(kept)} within-call repeats of the same metric, target and period")
    rows = kept
    count: Counter = Counter()
    for r in rows:
        count[r["ticker"]] += 1
        r["id"] = f"{r['ticker']}-{count[r['ticker']]:03d}"
        r["call_date"] = known[(r["ticker"], r["call_quarter"])]["call_date"]
    with open(STATEMENTS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in COLUMNS} for r in rows)
    return rows


def main(argv: list[str]) -> int:
    if argv[:1] == ["merge"]:
        rows = merge()
        print(f"read {len(read_parts())} part rows, wrote {len(rows)}")
    elif argv[1:]:
        rows = read_parts([Path(a) for a in argv[1:]])
    else:
        rows = read(STATEMENTS)
    bad = problems(rows)
    per = Counter((r["ticker"], r["call_quarter"]) for r in rows)
    for (t, q), n in sorted(per.items(), key=lambda kv: (kv[0][0], int(kv[0][1][4:]), kv[0][1])):
        print(f"{t} {q}: {n}")
    failed = len({b.split(":")[0] for b in bad})
    print(f"total rows: {len(rows)}; passed: {len(rows) - failed} of {len(rows)}")
    print("\n".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
