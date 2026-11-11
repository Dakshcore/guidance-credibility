"""Download daily prices for the return test. Run only after docs/prereg.md is written.

`python -m credibility.prices` fetches each company (NSE symbol) and the Nifty 500 from Yahoo Finance's public
chart endpoint, one request per symbol with a pause, and writes
  data/raw/prices/<TICKER>.json   the raw response
  data/prices.csv                 ticker, date, close, adj_close (dividend- and split-adjusted)
  data/sources_prices.csv         ticker, symbol, url, downloaded_at, rows, status
A symbol that fails is logged with its status and skipped.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone

import requests

from credibility.sources import ROOT
from credibility.statements import STATEMENTS, read

RAW = ROOT / "data" / "raw" / "prices"
PRICES = ROOT / "data" / "prices.csv"
LOG = ROOT / "data" / "sources_prices.csv"
INDEX = "NIFTY500"
INDEX_SYMBOL = "^CRSLDX"
START, END = "2022-05-01", "2026-06-30"
PAUSE = 2.0
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1d&events=div%7Csplit"


def _epoch(day: str) -> int:
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def parse(payload: dict) -> list[tuple[str, float, float]]:
    """(date, close, adj_close) rows from a chart response; days with no price are dropped."""
    res = payload["chart"]["result"][0]
    stamps = res.get("timestamp") or []
    close = res["indicators"]["quote"][0]["close"]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or close
    offset = res["meta"].get("gmtoffset", 0)
    rows = []
    for ts, c, a in zip(stamps, close, adj):
        if c is None or a is None:
            continue
        rows.append((datetime.fromtimestamp(ts + offset, timezone.utc).strftime("%Y-%m-%d"), float(c), float(a)))
    return rows


def fetch(ticker: str, symbol: str) -> tuple[list, dict]:
    url = URL.format(symbol=requests.utils.quote(symbol), p1=_epoch(START), p2=_epoch(END))
    log = {"ticker": ticker, "symbol": symbol, "url": url,
           "downloaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": 0, "status": ""}
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (research script)"}, timeout=30)
        if r.status_code != 200:
            log["status"] = f"http {r.status_code}"
            return [], log
        RAW.mkdir(parents=True, exist_ok=True)
        (RAW / f"{ticker}.json").write_text(r.text, encoding="utf-8")
        rows = parse(json.loads(r.text))
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as e:
        log["status"] = f"error: {type(e).__name__}"
        return [], log
    log["rows"], log["status"] = len(rows), "ok" if rows else "empty"
    return rows, log


def main() -> int:
    tickers = sorted({r["ticker"] for r in read(STATEMENTS)})
    jobs = [(INDEX, INDEX_SYMBOL)] + [(t, f"{t}.NS") for t in tickers]
    logs, out = [], []
    for ticker, symbol in jobs:
        rows, log = fetch(ticker, symbol)
        logs.append(log)
        out += [(ticker, *r) for r in rows]
        print(f"{ticker}: {log['status']} {log['rows']}", flush=True)
        time.sleep(PAUSE)
    with open(PRICES, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ticker", "date", "close", "adj_close"])
        w.writerows(out)
    with open(LOG, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(logs[0]))
        w.writeheader()
        w.writerows(logs)
    bad = [log["ticker"] for log in logs if log["status"] != "ok"]
    print(f"symbols: {len(jobs)}; ok: {len(jobs) - len(bad)}; failed: {', '.join(bad) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
