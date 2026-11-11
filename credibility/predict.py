"""Phase 3 tests, exactly as fixed in docs/prereg.md.

`python -m credibility.predict` reads data/credibility_yearly.csv, data/prices.csv and data/actuals_screener.csv
and writes
  data/panel.csv               one row per company-year: score, excess return, earnings surprise, split
  reports/phase3_results.txt   every test statistic with its sample size and 95% interval
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from scipy.stats import spearmanr

from credibility.prices import INDEX, PRICES
from credibility.sources import ROOT
from credibility.statements import read
from credibility.yearly import MIN_SCORED, OUT as YEARLY

PANEL = ROOT / "data" / "panel.csv"
RESULTS = ROOT / "reports" / "phase3_results.txt"
ACTUALS = ROOT / "data" / "actuals_screener.csv"
TRAIN, TEST = ("FY22", "FY23"), ("FY24", "FY25")
DRAWS, SEED = 2000, 20261111
SLACK_DAYS = 10  # a window end counts only if a trading day lies within this many days of it
COLUMNS = ["ticker", "fy", "split", "scored", "score", "scored_2y", "score_2y", "stock_return", "index_return",
           "excess_return", "excess_vs_sample", "surprise"]


def window(fy: str) -> tuple[date, date]:
    y = 2000 + int(fy[2:])
    return date(y, 6, 1), date(y + 1, 5, 31)


def window_return(series: list[tuple[date, float]], fy: str) -> float | None:
    """Return over the window from adjusted closes sorted by date, or None if either end has no price."""
    start, end = window(fy)
    inside = [(d, p) for d, p in series if start <= d <= end]
    if not inside:
        return None
    (d0, p0), (d1, p1) = inside[0], inside[-1]
    if d0 - start > timedelta(days=SLACK_DAYS) or end - d1 > timedelta(days=SLACK_DAYS):
        return None
    return p1 / p0 - 1


def surprise(actuals: dict[tuple[str, str], float], ticker: str, fy: str) -> float | None:
    y = int(fy[2:])
    now, nxt, sales = (actuals.get((ticker, k)) for k in (f"pat:FY{y}", f"pat:FY{y + 1}", f"revenue:FY{y}"))
    if now is None or nxt is None or not sales:
        return None
    return (nxt - now) / sales


def load_prices() -> dict[str, list[tuple[date, float]]]:
    out = defaultdict(list)
    for r in read(PRICES):
        out[r["ticker"]].append((date.fromisoformat(r["date"]), float(r["adj_close"])))
    return {t: sorted(v) for t, v in out.items()}


def build_panel() -> list[dict]:
    prices = load_prices()
    actuals = {(r["ticker"], r["key"]): float(r["value"]) for r in read(ACTUALS)}
    years = TRAIN + TEST
    stock = {(t, fy): window_return(s, fy) for t, s in prices.items() if t != INDEX for fy in years}
    index = {fy: window_return(prices[INDEX], fy) for fy in years}
    sample_mean = {fy: float(np.mean([v for (t, y), v in stock.items() if y == fy and v is not None]))
                   for fy in years if any(v is not None for (t, y), v in stock.items() if y == fy)}
    rows = []
    for r in read(YEARLY):
        fy = r["fy"]
        if fy not in years:
            continue
        ret, idx = stock.get((r["ticker"], fy)), index.get(fy)
        s = surprise(actuals, r["ticker"], fy)
        fmt = lambda v: "" if v is None else f"{v:.6f}"
        rows.append({"ticker": r["ticker"], "fy": fy, "split": "train" if fy in TRAIN else "test",
                     "scored": r["scored"], "score": r["score"], "scored_2y": r["scored_2y"],
                     "score_2y": r["score_2y"], "stock_return": fmt(ret), "index_return": fmt(idx),
                     "excess_return": fmt(None if ret is None or idx is None else ret - idx),
                     "excess_vs_sample": fmt(None if ret is None or fy not in sample_mean else ret - sample_mean[fy]),
                     "surprise": fmt(s)})
    return rows


def spearman(x: np.ndarray, y: np.ndarray, groups: np.ndarray | None = None) -> float:
    if len(x) < 3 or np.all(x == x[0]) or np.all(y == y[0]):
        return float("nan")
    return float(spearmanr(x, y).statistic)


def half_spread(x: np.ndarray, y: np.ndarray, groups: np.ndarray) -> float:
    """Mean outcome of rows above their year's median score minus the rest, pooled over years."""
    top, bottom = [], []
    for g in np.unique(groups):
        m = groups == g
        med = np.median(x[m])
        top += list(y[m][x[m] > med])
        bottom += list(y[m][x[m] <= med])
    if not top or not bottom:
        return float("nan")
    return float(np.mean(top) - np.mean(bottom))


def bootstrap(stat, x, y, groups, clusters, draws: int = DRAWS, seed: int = SEED) -> tuple[float, float, int]:
    """95% interval from resampling clusters (companies) with replacement; also the number of usable draws."""
    rng = np.random.default_rng(seed)
    names = np.unique(clusters)
    index = {n: np.flatnonzero(clusters == n) for n in names}
    vals = []
    for _ in range(draws):
        pick = np.concatenate([index[n] for n in rng.choice(names, size=len(names), replace=True)])
        v = stat(x[pick], y[pick], groups[pick])
        if not np.isnan(v):
            vals.append(v)
    if not vals:
        return float("nan"), float("nan"), 0
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi), len(vals)


def test(rows: list[dict], score: str, count: str, outcome: str, min_scored: int = MIN_SCORED) -> dict:
    use = [r for r in rows if int(r[count]) >= min_scored and r[outcome] != ""]
    out = {"n": len(use), "companies": len({r["ticker"] for r in use})}
    if len(use) < 3:
        return out
    x = np.array([float(r[score]) for r in use])
    y = np.array([float(r[outcome]) for r in use])
    g = np.array([r["fy"] for r in use])
    c = np.array([r["ticker"] for r in use])
    for name, stat in (("rho", spearman), ("spread", half_spread)):
        lo, hi, k = bootstrap(stat, x, y, g, c)
        out[name], out[name + "_ci"], out[name + "_draws"] = stat(x, y, g), (lo, hi), k
    return out


def fmt_test(label: str, t: dict) -> str:
    if "rho" not in t:
        return f"{label:<34} n={t['n']:<3} companies={t['companies']:<3} too few rows"
    return (f"{label:<34} n={t['n']:<3} companies={t['companies']:<3} "
            f"Spearman {t['rho']:+.3f} [{t['rho_ci'][0]:+.3f}, {t['rho_ci'][1]:+.3f}]  "
            f"top-minus-bottom {t['spread']:+.1%} [{t['spread_ci'][0]:+.1%}, {t['spread_ci'][1]:+.1%}]")


def lines(rows: list[dict]) -> list[str]:
    out = ["PHASE 3 RESULTS (definitions fixed in docs/prereg.md; intervals are 95%, bootstrap over companies, "
           f"{DRAWS} draws, seed {SEED})", ""]
    sets = (("test FY24-FY25", [r for r in rows if r["split"] == "test"]),
            ("train FY22-FY23", [r for r in rows if r["split"] == "train"]), ("pooled", rows))
    out.append(f"company-years in panel: {len(rows)}; with >= {MIN_SCORED} scored statements: "
               f"{sum(int(r['scored']) >= MIN_SCORED for r in rows)}; dropped by that rule: "
               f"{sum(int(r['scored']) < MIN_SCORED for r in rows)}")
    out.append(f"missing excess return: {sum(r['excess_return'] == '' for r in rows)}; "
               f"missing earnings surprise: {sum(r['surprise'] == '' for r in rows)}")
    for outcome, title in (("excess_return", "FORWARD 12-MONTH EXCESS RETURN VS NIFTY 500"),
                           ("surprise", "NEXT-YEAR EARNINGS SURPRISE (random-walk proxy, scaled by sales)")):
        out += ["", title, "primary specification"]
        out += [fmt_test(name, test(rs, "score", "scored", outcome)) for name, rs in sets]
        out.append("robustness: two-year score")
        out += [fmt_test(name, test(rs, "score_2y", "scored_2y", outcome)) for name, rs in sets]
        out.append("robustness: at least 5 scored statements")
        out += [fmt_test(name, test(rs, "score", "scored", outcome, 5)) for name, rs in sets]
        if outcome == "excess_return":
            out.append("robustness: excess over the equal-weighted sample mean return")
            out += [fmt_test(name, test(rs, "score", "scored", "excess_vs_sample")) for name, rs in sets]
    out += ["", "DESCRIPTION BY SCORE YEAR (company-years with >= %d scored statements)" % MIN_SCORED,
            f"{'year':<6}{'n':>4}{'median score':>14}{'mean score':>12}{'index return':>14}{'mean excess':>13}"
            f"{'median excess':>15}{'mean surprise':>15}"]
    for fy in TRAIN + TEST:
        rs = [r for r in rows if r["fy"] == fy and int(r["scored"]) >= MIN_SCORED]
        if not rs:
            continue
        sc = [float(r["score"]) for r in rs]
        ex = [float(r["excess_return"]) for r in rs if r["excess_return"] != ""]
        su = [float(r["surprise"]) for r in rs if r["surprise"] != ""]
        idx = next((r["index_return"] for r in rs if r["index_return"] != ""), "")
        out.append(f"{fy:<6}{len(rs):>4}{np.median(sc):>14.3f}{np.mean(sc):>12.3f}{float(idx):>14.1%}"
                   f"{np.mean(ex):>13.1%}{np.median(ex):>15.1%}{np.mean(su):>15.1%}")
    return out


if __name__ == "__main__":
    panel = build_panel()
    with open(PANEL, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(panel)
    text = "\n".join(lines(panel))
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(text + "\n", encoding="utf-8")
    print(text)
