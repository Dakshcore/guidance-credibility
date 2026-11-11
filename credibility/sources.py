"""Find and download earnings-call transcripts, and log every file in data/sources.csv.

Discovery: the public Screener.in company page lists each concall with a link to the transcript PDF
(usually the BSE filing, sometimes the company's investor page). We save that page under data/raw/screener/,
read the links, download each PDF once, and record url, call month, quarter, sha256 and page count.

`python -m credibility.sources TICKER [TICKER ...]` runs discovery and download for those tickers.
A quarter with no transcript link, or whose download fails, is written with status "missing" and the reason.
Gaps are never filled from another source silently.
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "screener"
PDF_DIR = ROOT / "data" / "transcripts"
SOURCES = ROOT / "data" / "sources.csv"
MANUAL = ROOT / "data" / "manual_sources.csv"
COLUMNS = ["ticker", "quarter", "call_month", "call_date", "url", "source_site", "file", "sha256", "pages",
           "downloaded_utc", "status", "note", "role"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/126.0 Safari/537.36"}
PAUSE = 2.0  # seconds between requests
MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1)}


def all_quarters(first: str = "Q1FY22", last: str = "Q4FY25") -> list[str]:
    out = []
    for fy in range(int(first[4:]), int(last[4:]) + 1):
        out += [f"Q{q}FY{fy}" for q in (1, 2, 3, 4)]
    return out[out.index(first): out.index(last) + 1]


def quarter_of(call_month: str) -> str:
    """The quarter a call discusses, from the month it was held: 'Aug 2023' -> Q1FY24."""
    mon, year = call_month.split()
    m, y = MONTHS[mon], int(year)
    if m in (7, 8, 9):
        return f"Q1FY{(y + 1) % 100:02d}"
    if m in (10, 11, 12):
        return f"Q2FY{(y + 1) % 100:02d}"
    if m in (1, 2, 3):
        return f"Q3FY{y % 100:02d}"
    return f"Q4FY{y % 100:02d}"


def parse_concalls(html: str) -> list[dict]:
    """[{call_month, url}] for every concall row on a Screener company page; url is '' if no transcript link."""
    start = html.find("Concalls</h3>")
    if start < 0:
        return []
    end = html.find("</ul>", start)
    out = []
    for li in re.findall(r"<li class=\"flex.*?</li>", html[start:end], flags=re.S):
        month = re.search(r">\s*([A-Z][a-z]{2} \d{4})\s*</div>", li)
        url = ""
        for attrs, text in re.findall(r"<a\b([^>]*)>(.*?)</a>", li, flags=re.S):
            href = re.search(r"href=\"([^\"]+)\"", attrs)
            if text.strip() == "Transcript" and href:
                url = href.group(1).replace("&amp;", "&")
        if month:
            out.append({"call_month": month.group(1), "url": url})
    return out


def fetch_page(ticker: str, refresh: bool = False) -> str:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{ticker}.html"
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    r = requests.get(f"https://www.screener.in/company/{ticker}/consolidated/", headers=HEADERS, timeout=60)
    r.raise_for_status()
    path.write_text(r.text, encoding="utf-8")
    time.sleep(PAUSE)
    return r.text


def download(url: str, dest: Path) -> tuple[str, str]:
    """Returns (status, note). Three attempts, then give up and say why."""
    headers = dict(HEADERS)
    if "bseindia.com" in url:
        headers["Referer"] = "https://www.bseindia.com/"
    note = ""
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=120)
            if r.status_code == 200 and r.content[:5] == b"%PDF-":
                dest.write_bytes(r.content)
                return "ok", ""
            note = f"HTTP {r.status_code}, first bytes {r.content[:8]!r}"
        except requests.RequestException as e:
            note = f"{type(e).__name__}"
        time.sleep(PAUSE * (attempt + 2))
    return "missing", f"download failed: {note}"


_MONTH = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = re.compile(rf"\b(?:({_MONTH}) (\d{{1,2}})(?:st|nd|rd|th)? ?, ?(\d{{4}})|(\d{{1,2}})(?:st|nd|rd|th)? ({_MONTH}),? (\d{{4}}))")
_PERIOD_ENDS = {(3, 31), (6, 30), (9, 30), (12, 31)}


def call_date(text: str) -> str:
    """The date printed most often in the transcript (page headers repeat the call date), as YYYY-MM-DD.

    Quarter-end dates are ignored: they are the reporting period, not the call."""
    from collections import Counter
    names = _MONTH.split("|")
    seen = Counter()
    for m in _DATE.finditer(" ".join(text.split())):
        mon, day, year = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(5), m.group(4), m.group(6))
        key = (int(year), names.index(mon) + 1, int(day))
        if (key[1], key[2]) not in _PERIOD_ENDS:
            seen[key] += 1
    if not seen:
        return ""
    top = max(seen.values())
    y, mo, d = min(k for k, n in seen.items() if n == top)  # tie: the call precedes the cover letter
    return f"{y:04d}-{mo:02d}-{d:02d}"


def read_sources() -> list[dict]:
    if not SOURCES.exists():
        return []
    with open(SOURCES, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_manual() -> list[dict]:
    if not MANUAL.exists():
        return []
    with open(MANUAL, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_sources(rows: list[dict]) -> None:
    rows.sort(key=lambda r: (r["ticker"], int(r["quarter"][4:]), r["quarter"]))
    with open(SOURCES, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in COLUMNS} for r in rows)


LATER = ("Q1FY26", "Q2FY27")  # calls after the study period: used only as sources of reported actuals


def collect(ticker: str, later: bool = False) -> list[dict]:
    import pypdf

    calls = {}
    for c in parse_concalls(fetch_page(ticker)):
        q = quarter_of(c["call_month"])
        # Two calls can map to one quarter (results call plus an analyst meet). Keep the earliest that has a
        # transcript link: the results call comes first. The page lists newest first, so later rows win.
        if q not in calls or c["url"] or not calls[q]["url"]:
            calls[q] = c
    for m in read_manual():  # hand-checked links win over the Screener list
        if m["ticker"] == ticker:
            calls[m["quarter"]] = {"call_month": m["call_month"], "url": m["url"], "note": m["found_via"]}
    rows = []
    for q in (all_quarters(*LATER) if later else all_quarters()):
        row = {"ticker": ticker, "quarter": q, "status": "missing", "role": "actuals" if later else "study"}
        c = calls.get(q)
        if c is None:
            row["note"] = "no concall listed on the Screener page"
        elif not c["url"]:
            row.update(call_month=c["call_month"], note=c.get("note") or "concall listed without a transcript link")
        else:
            dest = PDF_DIR / ticker / f"{q}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            row.update(call_month=c["call_month"], url=c["url"],
                       source_site=re.sub(r"^https?://(www\.)?([^/]+)/.*$", r"\2", c["url"]))
            if dest.exists():
                status, note = "ok", ""
            else:
                status, note = download(c["url"], dest)
                time.sleep(PAUSE)
            row.update(status=status, note=note or c.get("note", ""))
            if status == "ok":
                data = dest.read_bytes()
                try:
                    pages = len(pypdf.PdfReader(dest).pages)
                except Exception as e:  # unreadable PDF: keep the file, flag it
                    pages, row["status"], row["note"] = "", "missing", f"unreadable PDF: {type(e).__name__}"
                try:
                    row["call_date"] = call_date(" ".join(p.extract_text() or "" for p in pypdf.PdfReader(dest).pages))
                except Exception:
                    row["call_date"] = ""
                row.update(file=str(dest.relative_to(ROOT)).replace("\\", "/"),
                           sha256=hashlib.sha256(data).hexdigest(), pages=pages,
                           downloaded_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        rows.append(row)
    return rows


if __name__ == "__main__":
    later = "--later" in sys.argv
    tickers = [a for a in sys.argv[1:] if a != "--later"]
    role = "actuals" if later else "study"
    keep = [r for r in read_sources() if not (r["ticker"] in tickers and (r.get("role") or "study") == role)]
    for r in keep:
        r["role"] = r.get("role") or "study"
    for t in tickers:
        new = collect(t, later)
        keep += new
        write_sources(keep)
        ok = sum(r["status"] == "ok" for r in new)
        print(f"{t}: {ok} of {len(new)} quarters downloaded; missing: "
              + ", ".join(f"{r['quarter']} ({r['note']})" for r in new if r["status"] != "ok"))
