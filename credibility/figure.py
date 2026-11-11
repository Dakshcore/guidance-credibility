"""Figure for the note. `python -m credibility.figure` reads data/panel.csv and writes reports/figure1.png:
score against forward 12-month excess return, one point per company-year, train and test marked."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from credibility.predict import PANEL
from credibility.sources import ROOT
from credibility.statements import read
from credibility.yearly import MIN_SCORED

OUT = ROOT / "reports" / "figure1.png"

if __name__ == "__main__":
    rows = [r for r in read(PANEL) if int(r["scored"]) >= MIN_SCORED and r["excess_return"] != ""]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for split, colour, mark in (("train", "#8a8a8a", "o"), ("test", "#1f5aa6", "s")):
        rs = [r for r in rows if r["split"] == split]
        ax.scatter([float(r["score"]) for r in rs], [100 * float(r["excess_return"]) for r in rs],
                   c=colour, marker=mark, s=22, label=f"{split} (n={len(rs)})")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xlabel("Credibility score (share of scored guidance delivered in the year)")
    ax.set_ylabel("Forward 12-month excess return vs Nifty 500 (%)")
    ax.legend(frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT, dpi=200)
    print(f"{len(rows)} points -> {OUT.relative_to(ROOT)}")
