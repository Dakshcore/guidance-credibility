"""Turn the transcript PDFs into page-tagged text, so every quote can cite a page.

`python -m credibility.transcripts` writes data/transcripts/text/<TICKER>/<quarter>.txt with a
"=== page N ===" line before each PDF page. Page numbers are PDF pages (page 1 is often the exchange cover
letter), the same convention as the senco-initiation repo.
"""
from __future__ import annotations

import re
from pathlib import Path

import pypdf

from credibility.sources import ROOT, read_sources

TEXT_DIR = ROOT / "data" / "transcripts" / "text"


def normalise(s: str) -> str:
    """Lower-case, straight quotes and dashes, single spaces: for checking that a quote appears in the text."""
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("–", "-"),
                 ("—", "-"), (" ", " "), ("₹", "rs")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().lower()


def pdf_pages(path: Path) -> list[str]:
    return [" ".join((p.extract_text() or "").split()) for p in pypdf.PdfReader(path).pages]


def text_path(ticker: str, quarter: str) -> Path:
    return TEXT_DIR / ticker / f"{quarter}.txt"


def text_pages(ticker: str, quarter: str) -> dict[int, str]:
    """{page number: normalised text} from the page-tagged transcript."""
    out, page = {}, None
    for line in text_path(ticker, quarter).read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"=== page (\d+) ===", line)
        if m:
            page = int(m.group(1))
            out[page] = ""
        elif page is not None:
            out[page] += " " + line
    return {p: normalise(t) for p, t in out.items()}


def write_text() -> int:
    n = 0
    for r in read_sources():
        if r["status"] != "ok":
            continue
        dest = text_path(r["ticker"], r["quarter"])
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f"=== page {i} ===\n{t}" for i, t in enumerate(pdf_pages(ROOT / r["file"]), start=1))
        dest.write_text(body, encoding="utf-8")
        n += 1
    return n


if __name__ == "__main__":
    print(f"wrote {write_text()} new text files to {TEXT_DIR}")
