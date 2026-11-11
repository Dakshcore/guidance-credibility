# Scoring rubric

Version 1.0, frozen 2026-11-10 before any statement was scored. Changes after this point need the owner's
approval and a dated entry at the bottom of this file.

The rubric extends the one used in the senco-initiation repo (`senco/guidance.py`, `senco/delivery.py`,
`data/delivery_rules.csv`). Differences from that repo are listed in section 7.

## 1. What counts as guidance

A statement is guidance when all four hold:

1. It is said by company management on an earnings call (prepared remarks or Q&A). Analyst questions,
   moderator text and the exchange cover letter are not guidance.
2. It is about the future, or about a period that had not been reported when the call took place.
3. It names an outcome the company later reports or could report: a growth rate, a margin, a rupee amount,
   a count (stores, cities), a ratio, a date, or a clear direction (higher, lower, flat) against a named base.
4. It is the company's own expectation, plan, target, aspiration or commitment. Hedged wording
   ("we endeavour", "should be around", "we are confident of") still counts. The hedge goes in `notes`.

Not guidance, and not extracted:

- Descriptions of past or current results ("Q2 margin was 12%").
- Industry or macro views with no company outcome ("gold demand should stay strong").
- Pure strategy with no measurable outcome ("we will keep investing in the brand").
- A refusal to guide ("we do not give guidance on margins").
- Analyst suggestions that management does not adopt. If management answers "yes, that is right" to an
  analyst's number, the management reply is extracted and the note says the number came from the question.

Repeats are kept. If the same target is restated on a later call it is a new row, because the study measures
what management said on each call.

Within one call, the same target is recorded once. If management states the same metric, target and period
more than once on a call, the earliest page is kept (`credibility.statements merge` drops the rest and
prints how many).

## 2. Fields recorded for each statement

| Field | Rule |
|---|---|
| `ticker`, `call_quarter`, `call_date` | From `data/sources.csv`. |
| `speaker` | Surname or name as printed in the transcript. |
| `quote` | Verbatim from the transcript text, 10 to 45 words, from one PDF page. No ellipsis, no paraphrase, no stitched fragments. Transcript typos are kept. |
| `page` | PDF page number (page 1 is the first page of the file, often the cover letter). |
| `metric` | One of the list in section 3. |
| `target_value` | The target in words and numbers, e.g. `15-20%`, `~7%`, `>=35 stores`, `flat vs FY23`. |
| `target_period` | `FY24`, `Q3FY24`, `H2FY24`, `FY24-FY26`, a dated milestone such as `by Mar-25`, or `medium term` / `unspecified` when no date is given. |
| `notes` | Hedges, basis (standalone, segment, excluding bullion), and anything needed to score it. |

The quote and page must exist in the stored transcript. `python -m credibility.check` enforces this.

## 3. Metric list

`revenue_growth`, `revenue`, `sssg` (same-store or like-for-like growth), `gross_margin`, `ebitda_margin`,
`ebit_margin`, `pat_margin`, `ebitda_growth`, `pat_growth`, `pat`, `store_additions`, `store_count`, `capex`,
`debt`, `inventory`, `working_capital`, `tax_rate`, `mix` (share of a product, channel or format),
`costs` (a cost line or a one-off loss), `other`.

## 4. What is scorable

A statement is scorable when all three hold:

1. **A target that can be turned into a range.** A number, a range, a floor or ceiling, or a direction
   against a named base. "Healthy growth" is not scorable.
2. **A period that has ended and been reported.** Data are scored through the latest reported quarter in
   the downloaded sources. A dated period that has not been reported is `not due`. A statement with no date
   ("medium term", "over time", "going forward") is `not scorable`, reason "no period".
3. **A reported actual on the same basis, from a downloaded source.** Either a key in
   `data/actuals_screener.csv`, or a figure stated by management on a later call in the stored transcripts,
   with a verbatim quote and page. No figure is taken from memory or from a source not on disk.

If any of the three fails, the verdict is `not scorable` (or `not due`) and the reason is written down.
When in doubt, the statement is `not scorable`.

Specific cases:

- **Multi-year targets** ("20-25 stores a year for three years"): scored on the weakest completed year
  if every year in the span has ended, otherwise `not due`.
- **Conditional guidance** ("if gold prices stay stable, ..."): scored as stated. The condition is noted.
- **Basis mismatch**: if the guide is on one basis (standalone, a segment, excluding bullion) and the only
  available actual is on another, it is `not scorable`, unless management reports the figure on the guided
  basis on a later call.
- **Pipelines and intentions without a commitment** ("we have eight stores in the pipeline"): `not scorable`,
  reason "pipeline, not a commitment".
- **Same call, two different ranges**: score against the wider union, and note it.

## 5. Verdicts and tolerance bands

Each scorable statement is reduced to a range `[lo, hi]` (either end may be open) and a direction
(`better = higher` or `better = lower`).

| Guide as stated | Range used |
|---|---|
| A range, "15-20%" | lo = 15, hi = 20 |
| A point, "about 20%", "~7%", "20%" | point +/- 5% of the point (relative): 19 to 21; 6.65 to 7.35 |
| A floor, "at least 18%", "upwards of", "north of" | lo = 18, hi open |
| A ceiling, "not more than 350 cr", "below 1.2x" | lo open, hi = value |
| "High teens", "mid teens", "low teens" | 17-19, 14-16, 11-13 |
| "Double digit" | lo = 10, hi open |
| "High single digit", "mid single digit", "low single digit" | 7-9, 4-6, 1-3 |
| Direction against a base, "higher than last year" | change vs base: lo = 0, hi open (or the mirror: lo open, hi = 0) |
| "Flat", "maintain", "similar to" a base value | base +/- 5% of the base (relative) |

Counts (stores) guided as a point use the same +/- 5% band, rounded outward to whole units only if the guide
was a whole number and the band is narrower than one unit (so "~20 stores" is 19 to 21).

Verdict, given the actual:

- `better = higher`: actual above `hi` is **beat**; inside `[lo, hi]` is **met**; below `lo` is **missed**.
- `better = lower`: actual below `lo` is **beat**; inside is **met**; above `hi` is **missed**.
- With an open end there is no "beat" on that side: a floor that is cleared is **met**.

"Delivered" means met or beat. Comparisons use the unrounded actual from the source; a call figure is used
as stated.

Which actual is used when both exist: the figure management reports on the guided basis on a later call
(`basis = call`) is preferred when the guide is on a company-specific basis (store counts, SSSG, segment or
standalone numbers, adjusted margins). The Screener consolidated figure (`basis = screener`) is used for
consolidated revenue, EBITDA margin, PAT and balance-sheet guides. The row records which was used.

## 6. Output verdicts

`beat`, `met`, `missed`, `not scorable`, `not due`. Every `beat` / `met` / `missed` row carries
`actual_value` and `actual_source`. Every `not scorable` row carries a reason.

## 7. Differences from the senco-initiation rubric

1. The Senco repo has a separate verdict `no actual`. Here it is folded into `not scorable` with the reason
   "no reported actual". When the two scorecards are compared, `no actual` is mapped to `not scorable`.
2. The Senco repo marks undated statements `not due`. Here undated statements are `not scorable`
   (reason "no period"), because a statement with no date can never fall due. Both are unscored, so this
   does not change any delivery rate.
3. The Senco repo scored a few rows by hand (`manual_verdict`). Here a manual verdict is allowed only for
   `not scorable`; every `beat` / `met` / `missed` comes from the range rule in section 5.
4. Word-form guides ("high teens") have fixed ranges here (table in section 5). The Senco repo set them row
   by row.
5. The metric list is wider (section 3) to cover retail and QSR.

## Change log

- 2026-11-10: version 1.0 written and frozen.
- 2026-11-10: added the one-row-per-target-per-call rule (section 1). Made during extraction, before any
  statement was scored.
