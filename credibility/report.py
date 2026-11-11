"""Dataset numbers. `python -m credibility.report` prints them and writes reports/dataset_numbers.txt.

Everything is read from files in the repo: data/sources.csv, data/statements.csv, data/scores.csv,
data/token_usage.csv and universe.csv. Token usage covers subagents only (the main session is not metered).
reports/phase1_numbers.txt is the pilot-stage output of an earlier version of this script and is kept as is.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from credibility.score import SCORED, SCORES
from credibility.sources import ROOT, read_sources
from credibility.statements import STATEMENTS, read

OUT = ROOT / "reports" / "dataset_numbers.txt"


def fy(q: str) -> str:
    return q[2:]


def lines() -> list[str]:
    out = []
    src = read_sources()
    st = read(STATEMENTS)
    sc = {r["id"]: r for r in read(SCORES)} if SCORES.exists() else {}
    tickers = sorted({s["ticker"] for s in st})

    out.append("TRANSCRIPT COVERAGE (calls Q1FY22-Q4FY25 = 16 per company; later calls are actuals sources only)")
    out.append(f"{'ticker':<12}{'study ok':>9}{'no text':>8}{'missing':>8}{'later ok':>9}")
    tot = Counter()
    for t in tickers:
        mine = [r for r in src if r["ticker"] == t]
        c = Counter(ok=sum(r["role"] == "study" and r["status"] == "ok" for r in mine),
                    no_text=sum(r["role"] == "study" and r["status"] == "no_text" for r in mine),
                    miss=sum(r["role"] == "study" and r["status"] == "missing" for r in mine),
                    later=sum(r["role"] == "actuals" and r["status"] == "ok" for r in mine))
        tot.update(c)
        out.append(f"{t:<12}{c['ok']:>9}{c['no_text']:>8}{c['miss']:>8}{c['later']:>9}")
    out.append(f"{'ALL':<12}{tot['ok']:>9}{tot['no_text']:>8}{tot['miss']:>8}{tot['later']:>9}")
    out.append(f"companies: {len(tickers)}; with fewer than 12 study transcripts: "
               + (", ".join(t for t in tickers if sum(r["ticker"] == t and r["role"] == "study"
                                                      and r["status"] == "ok" for r in src) < 12) or "none"))

    out += ["", "STATEMENTS AND SCORES"]
    out.append(f"{'ticker':<12}{'stmts':>6}{'scored':>7}{'share':>7}{'beat':>6}{'met':>5}{'missed':>7}"
               f"{'not scorable':>13}{'not due':>8}{'delivered':>10}")
    groups = defaultdict(list)
    for s in st:
        groups[s["ticker"]].append(s)
        groups["ALL"].append(s)
    for t in tickers + ["ALL"]:
        v = Counter(sc[s["id"]]["verdict"] for s in groups[t] if s["id"] in sc)
        n, scored = len(groups[t]), sum(v[k] for k in SCORED)
        deliv = f"{(v['beat'] + v['met']) / scored:.1%}" if scored else "n/a"
        out.append(f"{t:<12}{n:>6}{scored:>7}{scored / n:>7.1%}{v['beat']:>6}{v['met']:>5}{v['missed']:>7}"
                   f"{v['not scorable']:>13}{v['not due']:>8}{deliv:>10}")
    unscored = sum(s["id"] not in sc for s in st)
    out.append(f"statements with no score row: {unscored}")

    out += ["", "SCORED SHARE BY CALL YEAR (all companies)"]
    by = defaultdict(Counter)
    for s in st:
        y = fy(s["call_quarter"])
        by[y]["n"] += 1
        by[y]["scored"] += s["id"] in sc and sc[s["id"]]["verdict"] in SCORED
    for y, c in sorted(by.items()):
        out.append(f"{y:<6}{c['scored']:>5} of {c['n']:<5}{c['scored'] / c['n']:>7.1%}")
    if sc:
        basis = Counter(r["basis"] for r in sc.values() if r["verdict"] in SCORED)
        out.append("")
        out.append("actual source of scored rows: " + ", ".join(f"{k} {v}" for k, v in sorted(basis.items())))

    use = read(ROOT / "data" / "token_usage.csv")
    kinds = Counter()
    for u in use:
        kinds[u["task"].split()[0]] += int(u["subagent_tokens"])
    out += ["", "TOKEN USAGE (subagents only; the main session is not metered by any tool)"]
    out.append(f"usage rows: {len(use)}; tokens recorded: {sum(kinds.values()):,} "
               f"({', '.join(f'{k} {v:,}' for k, v in sorted(kinds.items()))})")
    out.append("not recorded: the first Phase 2 extraction run (101 batches), which stopped with the app session "
               "before its usage was reported")

    uni = read(ROOT / "universe.csv")
    out += ["", f"UNIVERSE: {len(uni)} companies in universe.csv; by segment: "
            + ", ".join(f"{k} {v}" for k, v in sorted(Counter(u['segment'] for u in uni).items()))]
    extra = sorted(set(tickers) - {u["ticker"] for u in uni})
    out.append("in the dataset but outside universe.csv: " + (", ".join(extra) or "none"))

    sample = ROOT / "data" / "audit_sample.csv"
    if sample.exists():
        out += ["", f"audit sample: {len(read(sample))} scored statements in data/audit_sample.csv"]
    review = ROOT / "data" / "audit_review.csv"
    if review.exists():
        rv = read(review)
        c = Counter(r["audit_ok"].strip().lower() for r in rv)
        out += ["", f"INDEPENDENT AUDIT of data/audit_sample.csv ({len(rv)} rows reviewed by a separate agent): "
                + ", ".join(f"{k} {v}" for k, v in sorted(c.items()))]
        out += [f"  {r['id']}: {r['audit_ok']} - {r['audit_note']}" for r in rv if r["audit_ok"].strip().lower() != "yes"]
    ov = ROOT / "data" / "review_overrides.csv"
    if ov.exists():
        out += ["", f"review overrides (scored by an agent, set to not scorable on review): {len(read(ov))}"]
    return out


if __name__ == "__main__":
    text = "\n".join(lines())
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text + "\n", encoding="utf-8")
    print(text)
