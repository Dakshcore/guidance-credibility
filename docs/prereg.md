# Pre-registration: does guidance credibility predict returns and earnings?

Written on 2026-11-11, while Phase 2 scoring was still running and before any price or return data was
downloaded or opened. Nothing in this file may change after return data is loaded. Any later deviation is
recorded in docs/decisions.md with the reason, and the note reports it.

## Question

Do companies whose management delivered on past guidance earn higher returns, and report better earnings,
over the following year than companies that did not?

## Unit and sample

- Unit: one company in one fiscal year (April to March), written FYyy.
- Companies: every ticker with scored statements in data/scores.csv (the 40-company universe plus SENCO).
- A company-year enters the tests only if it has at least 3 scored statements (beat, met or missed) resolving
  in that year. The count of company-years dropped by this rule is reported.

## Credibility score

- A scored statement "resolves" in the fiscal year in which its target period ends. The year is read from
  `target_period` by `credibility.yearly.resolve_fy`: the last fiscal-year token (FY25, Q3FY25, H2FY25,
  FY24-FY26 -> FY26), or for "by Mon-yy" the fiscal year containing that month. Scored statements whose target
  period cannot be read this way are left out and counted.
- Score for company c in year y = (beat + met) / (beat + met + missed) over statements resolving in year y.
  Not scorable and not due rows play no part.
- Secondary score (reported, not the headline): the same share over statements resolving in year y or y-1.

This uses only outcomes that were public once FY y results were out, so the score is known before the
return window opens.

## Outcomes

1. Forward 12-month excess return. Window: 1 June after the end of FY y to 31 May of the next year (first and
   last trading day in the window). Stock return from dividend- and split-adjusted daily closes. Benchmark:
   Nifty 500. Excess return = stock return minus index return. If only a price index is available for the
   benchmark, that is stated in the note. Source: a free public price source, named in data/sources_prices.csv
   with URL and download date. A company with no price on either end of the window is dropped from that
   year and counted.
2. Next-year earnings surprise. No free consensus estimates exist for this sample, so the expectation is a
   random walk: surprise = (net profit FY y+1 minus net profit FY y) / sales FY y, consolidated, from the
   stored Screener annual figures (data/actuals_screener.csv). This is a proxy and the note says so.

## Split

- Train: score years FY22 and FY23 (return windows June 2022 to May 2023 and June 2023 to May 2024).
- Test: score years FY24 and FY25 (return windows June 2024 to May 2025 and June 2025 to May 2026).
- The train set is used only to check the code runs and to describe the data. No threshold, weight or
  definition is tuned on it. The definitions above are final.
- The reported result is the test set. Train results are shown beside it, labelled as such.

## Tests

For each outcome, on the test set, then on the train set, then pooled:

- Primary: Spearman rank correlation between score and outcome across company-years. Hypothesis: positive.
  95% confidence interval from a bootstrap that resamples companies (2,000 draws, seed 20261111), so the two
  years of one company stay together.
- Secondary: mean outcome of the top half minus the bottom half by score within each year, with the same
  bootstrap interval.
- Robustness, reported whatever it shows: the secondary score; minimum of 5 scored statements instead of 3;
  excess return measured against the equal-weighted mean return of the sample that year.

No other specifications will be run. Two outcomes are tested, so a single interval excluding zero at 95% is
weak evidence; the note says this. Sample size is reported for every number. A null or negative result is
reported as found.

## Known limits, stated in advance

- Small sample: at most 41 companies and two test years.
- The scored share of statements is low, so some company-years rest on few statements.
- FY22 scores are thin because the study starts with Q1 FY22 calls.
- The earnings surprise is a random-walk proxy, not a consensus surprise.
- Companies were chosen for transcript coverage, not at random.
