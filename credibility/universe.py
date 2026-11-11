"""Count in-period call transcripts for candidate companies and propose the full universe.

`python -m credibility.universe` fetches each candidate's public Screener.in page (saved under
data/raw/screener/), counts the quarters Q1FY22-Q4FY25 that have a transcript link, and writes
  data/universe_candidates.csv  every candidate with its count
  universe.csv                  the proposal: candidates with at least 12 transcripts, ranked by count then
                                market cap, cut at 40

The count is of transcript links listed on the page. Files are only downloaded in Phase 2, so a few links may
turn out dead or mislabelled; pilot companies use the count of files actually stored (data/sources.csv).
"""
from __future__ import annotations

import csv
import re
import sys

import requests

from credibility.sources import ROOT, all_quarters, fetch_page, parse_concalls, quarter_of, read_sources

CANDIDATES_OUT = ROOT / "data" / "universe_candidates.csv"
UNIVERSE = ROOT / "universe.csv"
MIN_TRANSCRIPTS, SIZE = 12, 40
PILOT = {"SENCO", "TITAN", "KALYANKJIL", "TRENT", "JUBLFOOD"}

# NSE symbol -> segment. Consumer discretionary: jewellery, retail, apparel and footwear, QSR, then
# durables, leisure and other consumer names to reach 40.
CANDIDATES = {
    "jewellery": "TITAN KALYANKJIL SENCO THANGAMAYL PCJEWELLER RAJESHEXPO VAIBHAVGBL GOLDIAM TBZ ETHOSLTD",
    "qsr": "JUBLFOOD DEVYANI SAPPHIRE WESTLIFE RBA BARBEQUE",
    "retail": "TRENT DMART VMART SHOPERSTOP ABFRL V2RETAIL SPENCERS MEDPLUS EMIL NYKAA ARVINDFASN",
    "apparel_footwear": "PAGEIND MANYAVAR GOCOLORS RAYMOND KKCL CANTABIL BATAINDIA RELAXO METROBRAND CAMPUS "
                        "DOLLAR LUXIND RUPA",
    "durables": "HAVELLS VOLTAS CROMPTON BLUESTARCO WHIRLPOOL BAJAJELEC TTKPRESTIG SYMPHONY ORIENTELEC VGUARD "
                "VIPIND SAFARI",
    "leisure": "PVRINOX INDHOTEL LEMONTREE CHALET",
    "home_paints": "ASIANPAINT BERGEPAINT KANSAINER CERA KAJARIACER",
}


def page_facts(html: str) -> tuple[str, float | None]:
    name = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.S)
    cap = re.search(r"Market Cap.*?<span class=\"number\">([\d,\.]+)</span>", html, flags=re.S)
    return (re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", name.group(1))).strip() if name else "",
            float(cap.group(1).replace(",", "")) if cap else None)


def count(ticker: str) -> dict:
    try:
        html = fetch_page(ticker)
    except requests.RequestException as e:
        return {"ticker": ticker, "company": "", "market_cap_cr": "", "transcripts_in_period": "",
                "missing_quarters": "", "note": f"page not fetched: {e}"}
    name, cap = page_facts(html)
    period = all_quarters()
    have = {quarter_of(c["call_month"]) for c in parse_concalls(html) if c["url"]} & set(period)
    note = "count of transcript links on the Screener page"
    if ticker in PILOT:
        have = {r["quarter"] for r in read_sources() if r["ticker"] == ticker and r["status"] == "ok"
                and r["role"] == "study"}
        note = "pilot: count of transcripts stored in data/sources.csv"
    return {"ticker": ticker, "company": name, "market_cap_cr": "" if cap is None else f"{cap:.0f}",
            "transcripts_in_period": len(have), "missing_quarters": " ".join(q for q in period if q not in have),
            "note": note}


def build() -> tuple[list[dict], list[dict]]:
    rows = []
    for segment, tickers in CANDIDATES.items():
        for t in tickers.split():
            rows.append({"segment": segment, **count(t)})
            print(f"{t}: {rows[-1]['transcripts_in_period']}", flush=True)
    cols = ["ticker", "company", "segment", "market_cap_cr", "transcripts_in_period", "missing_quarters", "note"]
    ok = [r for r in rows if r["transcripts_in_period"] != "" and r["transcripts_in_period"] >= MIN_TRANSCRIPTS]
    ok.sort(key=lambda r: (-r["transcripts_in_period"], -float(r["market_cap_cr"] or 0)))
    chosen = ok[:SIZE]
    for path, data in ((CANDIDATES_OUT, rows), (UNIVERSE, chosen)):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(data)
    return rows, chosen


if __name__ == "__main__":
    rows, chosen = build()
    fetched = [r for r in rows if r["transcripts_in_period"] != ""]
    print(f"candidates: {len(rows)}; pages fetched: {len(fetched)}; with >= {MIN_TRANSCRIPTS} transcripts: "
          f"{sum(r['transcripts_in_period'] >= MIN_TRANSCRIPTS for r in fetched)}; in universe.csv: {len(chosen)}")
    sys.exit(0)
