# Extraction brief (given to every extraction agent)

Work only inside `C:\Users\daksh\projects\guidance-credibility`. Do not read or write anywhere else. Do not
use the web. Do not commit. Do not edit any file other than your own output file and helper files in `scratch/`.

1. Read `docs/rubric.md` sections 1 to 3. They define what counts as guidance and the fields.
2. For each call assigned to you, read the whole transcript text at
   `data/transcripts/text/<TICKER>/<QUARTER>.txt`. Pages are marked `=== page N ===`.
3. Extract every management statement that meets rubric section 1. Be complete: prepared remarks and Q&A.
   Keep repeats across calls, but within one call record the same metric, target and period only once
   (the first time it is said). Skip analyst and moderator text. Typical yield is 8 to 25 rows per call.
4. Write the rows to the output CSV you were given, with exactly these columns:
   `call_quarter,page,speaker,quote,metric,target_value,target_period,notes`
   - `quote`: copied character for character from one page of the text file, 10 to 45 words, one contiguous
     span. No ellipsis, no paraphrase, no fixing typos. Pick the span that carries the number or target.
   - `page`: the N of the `=== page N ===` marker the quote sits under.
   - `metric`: one value from rubric section 3.
   - `target_value`: short, e.g. `15-20%`, `~7%`, `>=35 stores`, `higher than FY23`.
   - `target_period`: `FY24`, `Q3FY24`, `H2FY24`, `FY24-FY26`, `by Mar-25`, `medium term` or `unspecified`.
     Indian fiscal year: FY24 ends March 2024. Work out the period from the call quarter when management says
     "this year" or "next quarter" (the call for Q1FY24 is held in Jul-Sep 2023).
   - `notes`: hedges, basis (standalone, segment, ex-bullion), and whether the number came from the analyst.
   Write the CSV with Python's `csv` module (a script in `scratch/`), UTF-8, so quoting is correct.
5. Run the checker and fix every failure, until it prints `passed: N of N`:
   `cd /c/Users/daksh/projects/guidance-credibility && python -m credibility.statements check <your csv>`
   A quote that fails must be re-copied from the text, or the row dropped. Never loosen the checker.
6. Do not score anything and do not look up actual results.

Reply in under 80 words: rows per call, and the checker's `total rows` line.
