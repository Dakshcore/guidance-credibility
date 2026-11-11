# Scoring brief (given to every scoring agent)

Work only inside `C:\Users\daksh\projects\guidance-credibility`. Do not read or write anywhere else. Do not
use the web. Do not commit. Edit only your own output file and helper files in `scratch/`.

You do not decide beat / met / missed. You write, for each statement, the guided range as numbers and where
the reported actual is. A script computes the verdict.

1. Read `docs/rubric.md` sections 4 to 6.
2. Your statements are the rows of `data/statements.csv` for your ticker and call quarters.
3. For every statement id, write one row to your output CSV with exactly these columns:
   `id,lo,hi,better,basis,screener_key,actual_num,actual_text,src_call,src_page,src_quote,src2_call,src2_page,src2_quote,verdict_override,reason`
   - `lo`, `hi`: the range from rubric section 5 (a point guide is the point +/- 5% of itself; leave an open
     end empty). Same unit as the actual: per cent for margins and growth, Rs crore for money, a count for stores.
   - `better`: `higher` or `lower` (lower for debt, costs, losses, inventory days and similar).
   - `basis`:
     - `screener`: the actual is a key in `data/actuals_screener.csv` for your ticker. Put the key in
       `screener_key` (e.g. `rev_growth:FY24`, `q_ebitda_margin:Q3FY25`). Grep the file to see the keys that
       exist. These are consolidated figures; use them only when the guide is on a consolidated basis.
     - `call`: management reported the outcome on a later call. Search the later transcripts of your ticker in
       `data/transcripts/text/<TICKER>/` (they run to Q1FY27) with Grep, then read the page. Give `actual_num`
       (a plain number), `actual_text` (number with unit, e.g. `75 stores`), `src_call` (e.g. `Q4FY24`),
       `src_page`, and `src_quote`: 8 to 45 words copied character for character from that page, containing
       the figure. If the actual needs two reported figures (closing count minus opening count), give the
       second in `src2_*` and say how you combined them in `reason`.
     - `none`: not scored. `verdict_override` is `not scorable` or `not due`, and `reason` says why in a few
       words (e.g. `no period`, `no numeric target`, `no reported actual on the guided basis`,
       `pipeline, not a commitment`, `FY27 not yet reported`). Leave lo, hi, better empty.
   - Leave `verdict_override` empty unless basis is `none`.
4. What is reported so far: Screener has annual figures to FY26 and quarters to Q2FY27; transcripts run to the
   Q1FY27 call. A target period that ends after that is `not due`.
5. Evidence rules. Never use a figure from memory. The actual must be a Screener key or a quote that is in a
   stored transcript. The actual must be on the same basis and for the same period as the guide. If you cannot
   find it after a real search, or you are unsure the bases match, mark it `not scorable` with the reason.
   It is fine for many rows to be `not scorable`. Do not stretch.
6. Write the CSV with Python's `csv` module (a script in `scratch/`), UTF-8. Then run the checker and fix
   every problem it prints, until it prints a summary line for your ticker:
   `cd /c/Users/daksh/projects/guidance-credibility && python -m credibility.score check <your csv>`

Reply in under 80 words: rows written, how many of each basis, and the checker's summary line.
