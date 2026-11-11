# Guidance credibility study

Do listed Indian consumer and retail companies deliver on what management says on earnings calls, and does a
delivery score predict returns or earnings? This repo extracts forward-looking statements from call
transcripts (Q1 FY22 to Q4 FY25), scores them against later reported numbers, builds a yearly credibility
score per company, and tests it. It extends the method of the Senco Gold study (`senco-initiation`).

**Result.** No relation found. In the pre-registered test years the rank correlation between the score and
forward 12-month excess return over the Nifty 500 is -0.030 (95% interval -0.342 to +0.260, n=57). For
next-year earnings surprise it is -0.062 (-0.417 to +0.272, n=49). The full write-up, with limits, is in
`reports/guidance_credibility_note.md`.

**Dataset.** 41 companies, 565 transcripts, 6,959 statements each with a verbatim quote and page number,
1,107 scored (151 beat, 427 met, 529 missed).

## Layout

| Path | What it is |
|---|---|
| `universe.csv` | The 40 approved companies (Senco, the pilot, is extra). |
| `data/sources.csv` | Every transcript: URL, download date, status. |
| `data/transcripts/` | Page-tagged transcript text. Not in this repo, see below. |
| `data/statements.csv` | One row per guidance statement: quote, page, metric, target, period. |
| `data/scoring_parts/` | Rule rows per company: guided range, reported outcome, source. |
| `data/review_overrides.csv` | Rows moved to not scorable on review, with reasons. |
| `data/scores.csv` | Statements with computed verdicts. |
| `data/actuals_screener.csv` | Reported annual and quarterly figures from Screener.in. |
| `data/audit_sample.csv` | Random sample of 50 scored statements for hand checking. |
| `data/credibility_yearly.csv` | Score per company and fiscal year. |
| `data/prices.csv`, `data/sources_prices.csv` | Daily prices from Yahoo Finance and the download log. |
| `data/panel.csv` | Company-years with score, excess return and earnings surprise. |
| `docs/rubric.md` | What counts as guidance and how it is scored. Frozen before scoring. |
| `docs/prereg.md` | Test design, written before price data was downloaded. |
| `docs/decisions.md` | Every judgment call, dated. |
| `reports/` | The note, the figure, and the script outputs every number comes from. |

## Run

Python (`3.13` was used) with pandas, NumPy, SciPy, Matplotlib, pytest, pypdf and requests.

```
python -m pytest                 # scoring logic, quote check, yearly score, tests, trace
python -m credibility.check      # every quote is on its page; every scored row has a sourced actual
python -m credibility.review     # apply review overrides to the rule files
python -m credibility.score      # merge rule files into data/scores.csv
python -m credibility.audit      # draw the audit sample
python -m credibility.yearly     # yearly scores
python -m credibility.predict    # panel and test results -> reports/phase3_results.txt
python -m credibility.figure     # reports/figure1.png
python -m credibility.report     # dataset numbers -> reports/dataset_numbers.txt
python -m credibility.trace      # every number in the note and this file has a script source
```

`python -m credibility.prices` re-downloads prices (one request per symbol, with a pause). Transcript
download and text extraction are in `credibility/sources.py` and `credibility/transcripts.py`.

## What is not in this repo

The transcript PDFs, their extracted text (`data/transcripts/`) and the saved Screener.in and Yahoo Finance
pages (`data/raw/`) are third-party material and are not published here. `data/sources.csv` and
`data/sources_prices.csv` list the URL of every file. Without them, `python -m credibility.check` and
`python -m credibility.score` cannot run on a fresh clone; `credibility/sources.py` and
`credibility/transcripts.py` download and extract the transcripts again. The test suite and everything
from `data/scores.csv` onward (yearly score, tests, figure, report, trace) run from the files that are here.

## How statements were extracted and scored

Language-model agents read each transcript under `docs/extraction_brief.md` and `docs/scoring_brief.md`.
They write quotes, guided ranges and reported outcomes. They do not write verdicts: `credibility/score.py`
computes those. Scripts verify that each quote exists on its page and that each scored row names its source.
The judgment of what range a sentence implies is the agent's and is not verified beyond the audit sample.

## Limits

Small sample, a low scored share, uneven scoring depth across companies, a price-index benchmark, a
random-walk earnings proxy, and unadjusted demergers (Raymond, ABFRL). See the note.
