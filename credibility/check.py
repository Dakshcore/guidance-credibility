"""The target-state checks in one command: `python -m credibility.check`.

1. Every row in data/statements.csv has a verbatim quote that is on the cited page of the stored transcript.
2. Every scored row in data/scores.csv has an actual value and a named source, and every statement has a row.
Exit code 0 only if both pass.
"""
from __future__ import annotations

import sys

from credibility import score, statements


def run() -> tuple[list[str], str]:
    rows = statements.read(statements.STATEMENTS)
    bad = statements.problems(rows)
    lines = [f"statements: {len(rows)} rows, {len(rows) - len({b.split(':')[0] for b in bad})} pass the quote check"]
    if score.SCORES.exists():
        scores = statements.read(score.SCORES)
        sbad = score.output_problems(scores)
        ids, sids = {r["id"] for r in rows}, {r["id"] for r in scores}
        sbad += [f"{i}: statement without a score row" for i in sorted(ids - sids)]
        sbad += [f"{i}: score row without a statement" for i in sorted(sids - ids)]
        scored = [r for r in scores if r["verdict"] in score.SCORED]
        lines.append(f"scores: {len(scores)} rows, {len(scored)} scored, "
                     f"{len(scored) - len({b.split(':')[0] for b in sbad} & {r['id'] for r in scored})} "
                     f"with actual value and named source")
        bad += sbad
    else:
        lines.append("scores: data/scores.csv not built yet")
    return bad, "\n".join(lines)


if __name__ == "__main__":
    problems, text = run()
    print(text)
    print("\n".join(problems))
    print("CHECK PASSED" if not problems else f"CHECK FAILED: {len(problems)} problems")
    sys.exit(1 if problems else 0)
