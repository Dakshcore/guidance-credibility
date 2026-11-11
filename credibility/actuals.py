"""Reported figures from the saved Screener.in company pages, as a keyed table.

`python -m credibility.actuals` reads data/raw/screener/<TICKER>.html (consolidated page, saved by
credibility.sources) and writes data/actuals_screener.csv with one row per (ticker, key):

  annual      revenue:FY24  rev_growth:FY24  ebitda:FY24  ebitda_margin:FY24  ebitda_growth:FY24
              ebitda_change_bps:FY24  pbt:FY24  pat:FY24  pat_growth:FY24  pat_margin:FY24  tax_rate:FY24
              eps:FY24  borrowings:FY24  borrowing_change:FY24  de:FY24  inventory_days:FY24
              working_capital_days:FY24  roce:FY24  cfo:FY24  fcf:FY24  other_income:FY24
  quarterly   q_revenue:Q3FY24  q_rev_growth:Q3FY24  q_ebitda:Q3FY24  q_ebitda_margin:Q3FY24
              q_ebitda_growth:Q3FY24  q_pat:Q3FY24  q_pat_growth:Q3FY24  q_pat_margin:Q3FY24
  half-year   h1_revenue:FY25  h2_revenue:FY25  h1_rev_growth:FY25  h2_rev_growth:FY25
              h1_ebitda_margin:FY25  h2_ebitda_margin:FY25

Money is in Rs crore, margins and growth in per cent, changes in basis points. "EBITDA" is Screener's
operating profit (before other income). Margins are recomputed from the rupee rows, not read from the rounded
"OPM %" row. Growth needs the prior period on the page; if it is not there, the key is not written.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "screener"
OUT = ROOT / "data" / "actuals_screener.csv"
MONTH_Q = {"Jun": 1, "Sep": 2, "Dec": 3, "Mar": 4}


def _clean(cell: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", cell)).strip()


def _num(cell: str) -> float | None:
    cell = cell.replace(",", "").replace("%", "").replace("+", "").strip()
    try:
        return float(cell)
    except ValueError:
        return None


def table(html: str, section: str) -> dict[str, dict[str, float]]:
    """{row label: {column header: value}} for one section of the page (first table only)."""
    i = html.find(f'<section id="{section}"')
    if i < 0:
        return {}
    block = html[i: html.find("</table>", i)]
    heads = [_clean(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", block, flags=re.S)][1:]
    out = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, flags=re.S):
        cells = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)]
        if len(cells) < 2:
            continue
        label = cells[0].replace("+", "").strip()
        out[label] = {h: v for h, c in zip(heads, cells[1:]) if (v := _num(c)) is not None}
    return out


def fy(col: str) -> str | None:
    """'Mar 2024' -> 'FY24'. Other year-ends (and TTM) are skipped."""
    m = re.fullmatch(r"Mar (\d{4})", col)
    return f"FY{int(m.group(1)) % 100:02d}" if m else None


def quarter(col: str) -> str | None:
    """'Dec 2023' -> 'Q3FY24'."""
    m = re.fullmatch(r"(Jun|Sep|Dec|Mar) (\d{4})", col)
    if not m:
        return None
    year = int(m.group(2)) + (0 if m.group(1) == "Mar" else 1)
    return f"Q{MONTH_Q[m.group(1)]}FY{year % 100:02d}"


def _prev_fy(f: str) -> str:
    return f"FY{int(f[2:]) - 1:02d}"


def _prev_q(q: str) -> str:
    return f"{q[:4]}{int(q[4:]) - 1:02d}"


def keys(html: str) -> dict[str, float]:
    out: dict[str, float] = {}
    pnl, bs, cf, ratios, qt = (table(html, s) for s in ("profit-loss", "balance-sheet", "cash-flow", "ratios",
                                                         "quarters"))

    def series(tbl, label, conv):
        return {conv(c): v for c, v in tbl.get(label, {}).items() if conv(c)}

    sales, op, pat = series(pnl, "Sales", fy), series(pnl, "Operating Profit", fy), series(pnl, "Net Profit", fy)
    for name, s in (("revenue", sales), ("ebitda", op), ("pat", pat), ("pbt", series(pnl, "Profit before tax", fy)),
                    ("tax_rate", series(pnl, "Tax %", fy)), ("eps", series(pnl, "EPS in Rs", fy)),
                    ("other_income", series(pnl, "Other Income", fy)),
                    ("borrowings", series(bs, "Borrowings", fy)),
                    ("inventory_days", series(ratios, "Inventory Days", fy)),
                    ("working_capital_days", series(ratios, "Working Capital Days", fy)),
                    ("roce", series(ratios, "ROCE %", fy)),
                    ("cfo", series(cf, "Cash from Operating Activity", fy)),
                    ("fcf", series(cf, "Free Cash Flow", fy))):
        for f, v in s.items():
            out[f"{name}:{f}"] = v
    equity, reserves, borrow = (series(bs, k, fy) for k in ("Equity Capital", "Reserves", "Borrowings"))
    for f in sales:
        p = _prev_fy(f)
        if f in op and sales[f]:
            out[f"ebitda_margin:{f}"] = op[f] / sales[f] * 100
        if f in pat and sales[f]:
            out[f"pat_margin:{f}"] = pat[f] / sales[f] * 100
        if f in borrow and f in equity and f in reserves and equity[f] + reserves[f] > 0:
            out[f"de:{f}"] = borrow[f] / (equity[f] + reserves[f])
        if p in sales and sales[p]:
            out[f"rev_growth:{f}"] = (sales[f] / sales[p] - 1) * 100
            if f in op and p in op and op[p] > 0:
                out[f"ebitda_growth:{f}"] = (op[f] / op[p] - 1) * 100
                out[f"ebitda_change_bps:{f}"] = (op[f] / sales[f] - op[p] / sales[p]) * 10000
            if f in pat and p in pat and pat[p] > 0:
                out[f"pat_growth:{f}"] = (pat[f] / pat[p] - 1) * 100
            if f in borrow and p in borrow:
                out[f"borrowing_change:{f}"] = borrow[f] - borrow[p]

    qs, qop, qpat = (series(qt, k, quarter) for k in ("Sales", "Operating Profit", "Net Profit"))
    for q in qs:
        p = _prev_q(q)
        out[f"q_revenue:{q}"] = qs[q]
        if q in qop:
            out[f"q_ebitda:{q}"] = qop[q]
            if qs[q]:
                out[f"q_ebitda_margin:{q}"] = qop[q] / qs[q] * 100
        if q in qpat:
            out[f"q_pat:{q}"] = qpat[q]
            if qs[q]:
                out[f"q_pat_margin:{q}"] = qpat[q] / qs[q] * 100
        if p in qs and qs[p]:
            out[f"q_rev_growth:{q}"] = (qs[q] / qs[p] - 1) * 100
            if q in qop and p in qop and qop[p] > 0:
                out[f"q_ebitda_growth:{q}"] = (qop[q] / qop[p] - 1) * 100
            if q in qpat and p in qpat and qpat[p] > 0:
                out[f"q_pat_growth:{q}"] = (qpat[q] / qpat[p] - 1) * 100
    years = sorted({q[2:] for q in qs})
    for f in years:
        for half, members in (("h1", ("Q1", "Q2")), ("h2", ("Q3", "Q4"))):
            cur = [m + f for m in members]
            prev = [_prev_q(c) for c in cur]
            if all(c in qs for c in cur):
                rev = sum(qs[c] for c in cur)
                out[f"{half}_revenue:{f}"] = rev
                if all(c in qop for c in cur) and rev:
                    out[f"{half}_ebitda_margin:{f}"] = sum(qop[c] for c in cur) / rev * 100
                if all(c in qs for c in prev):
                    out[f"{half}_rev_growth:{f}"] = (rev / sum(qs[c] for c in prev) - 1) * 100
    return out


def load() -> dict[tuple[str, str], float]:
    with open(OUT, newline="", encoding="utf-8") as fh:
        return {(r["ticker"], r["key"]): float(r["value"]) for r in csv.DictReader(fh)}


def build(tickers: list[str] | None = None) -> int:
    paths = sorted(RAW.glob("*.html"))
    rows = []
    for p in paths:
        if tickers and p.stem not in tickers:
            continue
        for k, v in sorted(keys(p.read_text(encoding="utf-8")).items()):
            rows.append({"ticker": p.stem, "key": k, "value": round(v, 4),
                         "source": f"Screener.in consolidated page, data/raw/screener/{p.name}"})
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ticker", "key", "value", "source"])
        w.writeheader()
        w.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    print(f"wrote {build(sys.argv[1:] or None)} rows to {OUT}")
