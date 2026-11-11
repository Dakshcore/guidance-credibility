"""Trace every number in the note and README to a script output.

`python -m credibility.trace` reads reports/guidance_credibility_note.md and README.md, pulls out every
number, and checks that each one appears in a file a script wrote (reports/*.txt) or in the frozen
definitions (docs/prereg.md). Exit code 1 if any number has no source. Tokens glued to letters (FY24, Q1,
p7), ISO dates and inline code spans are labels, not figures, and are skipped.
"""
from __future__ import annotations

import re
import sys

from credibility.sources import ROOT

DOCS = [ROOT / "reports" / "guidance_credibility_note.md", ROOT / "README.md"]
SOURCES = [ROOT / "reports" / n for n in ("dataset_numbers.txt", "phase3_results.txt", "yearly_numbers.txt",
                                           "phase1_senco_validation.txt")] + [ROOT / "docs" / "prereg.md"]
TOKEN = re.compile(r"(?<![A-Za-z0-9.])[+-]?\d[\d,]*(?:\.\d+)?%?(?![A-Za-z0-9])")
CODE = re.compile(r"`[^`]*`")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def numbers(text: str) -> list[str]:
    """Numbers in the text, normalised: no thousands commas, no plus sign; a minus counts only as a sign."""
    text = DATE.sub(" ", CODE.sub(" ", text))
    out = []
    for m in TOKEN.finditer(text):
        tok = m.group().replace(",", "")
        if tok[0] in "+-":
            before = text[m.start() - 1] if m.start() else " "
            if tok[0] == "+" or before not in " [(|\n":
                tok = tok[1:]
        out.append(tok)
    return out


def untraced(doc: str, sources: list[str]) -> list[str]:
    known = {n for s in sources for n in numbers(s)}
    return sorted({n for n in numbers(doc) if n not in known})


if __name__ == "__main__":
    src = [p.read_text(encoding="utf-8") for p in SOURCES if p.exists()]
    bad = 0
    for d in DOCS:
        if not d.exists():
            print(f"{d.name}: missing")
            bad += 1
            continue
        found = numbers(d.read_text(encoding="utf-8"))
        miss = untraced(d.read_text(encoding="utf-8"), src)
        bad += len(miss)
        print(f"{d.name}: {len(found)} numbers, {len(found) - sum(n in miss for n in found)} traced; "
              f"untraced: {', '.join(miss) or 'none'}")
    print("TRACE PASSED" if not bad else "TRACE FAILED")
    sys.exit(1 if bad else 0)
