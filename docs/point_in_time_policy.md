# Point-in-Time and Fiscal-Period Policy

## Required dates

Every financial observation retains:

- `period_start` and `period_end`: period measured by the fact.
- `fiscal_year` and `fiscal_quarter`: issuer-relative FQ1–FQ4 identifiers.
- `filed_at`: SEC filing timestamp/date.
- `available_at`: earliest conservative timestamp at which the pipeline permits use.
- `accession_number`, `form_type`, amendment flag, XBRL tag, unit, and context.

Fiscal labels standardize position within an issuer's year but never replace actual dates. A join
at decision time `t` may use a record only when `available_at <= t`.

## Quarterly duration facts

Where a 10-K reports a full-year duration value but not standalone FQ4:

```text
FQ4 = FY − FQ1 − FQ2 − FQ3
```

The derived value inherits the 10-K availability timestamp and receives `is_derived_fq4 = true`.
Instant balance-sheet facts are never derived with this subtraction.

## Amendments and restatements

- Preserve original and amended facts as separate accession-aware records.
- A restated value is not eligible before its filing availability date.
- When multiple facts are eligible, selection follows a documented deterministic priority rule.
- Backtests must be reproducible using only the facts eligible at each decision date.

## Validation invariants

- No `available_at` later than its matched `decision_at`.
- No `filed_at` before `period_end`.
- Unique analytical key at company and decision date.
- No future macro vintage in historical rows.
- Preprocessing and feature selection fit separately within each temporal training fold.
