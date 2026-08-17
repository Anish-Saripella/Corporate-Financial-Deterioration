# Phase 1 Data Card

## Dataset purpose and population

The analytical dataset supports early warning of deterioration in corporate debt-service
capacity. It contains quarterly, filing-aware observations for 60 currently listed US issuers:
30 Consumer Discretionary and 30 Utilities companies selected by seeded stratified sampling after
strict eligibility screening. It is a research dataset, not a representative sample of all US
borrowers, defaults, or bank exposures.

## Sources and time coverage

Company identity, filing metadata, and XBRL facts come from free SEC EDGAR endpoints. Interest
rates, yield-curve, credit-spread, labor, industrial-production, and retail-sales measures come
from FRED/ALFRED. The study targets fiscal-quarter history from 2012 through the locally cached
cutoff. Every acquisition has a SHA-256 manifest; the final local financial store contains only
the selected universe to minimize redundant requests.

## Grain and point-in-time construction

One row is one company fiscal quarter with a unique `decision_key`. Fiscal quarters standardize
non-calendar fiscal years, while actual period-end and filing-availability dates are retained.
Financial facts and macro observations are joined only when available by the decision date.
Trailing-four-quarter KPIs are constructed from standalone quarters after FQ4 derivation and
reconciliation. The certified panel has 3,150 rows and no detected financial or macro leakage.

## Core measures and label

Interest coverage equals TTM operating income divided by valid TTM interest expense and is a
multiple. Free-cash-flow margin equals TTM operating cash flow less capital expenditures divided
by TTM revenue. Leverage equals total debt divided by total assets and is a proportion. The label
is one only when, during the next four fiscal quarters, interest coverage falls below 1.5x and is
at least 40% below its current value. It measures deterioration, not bankruptcy or default.

## Quality controls and known bias

Each company must pass KPI coverage, continuity, lineage, denominator, and temporal checks; 14
initial selections were replaced using the frozen reserve procedure. Delisted companies are
excluded, creating survivorship bias. Public XBRL variation, restatements, approximate macro
release availability, overlapping outcome windows, and two-sector coverage limit generalization.
Missing values are preserved and handled inside each training fold rather than globally imputed.

## Redistribution and refresh

Derived publication tables are suitable for public portfolio demonstration. Raw SEC/FRED downloads,
most processed Parquet tables, and serialized models remain ignored because they are reproducible
and can be large. Refreshes must preserve source usage policies, manifests, eligibility rules, and
the frozen holdout boundary; a changed universe or label requires a new version.
