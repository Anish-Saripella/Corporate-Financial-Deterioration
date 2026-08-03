# Phase 1 Chronological Implementation Plan

## Objective

Build a reproducible, point-in-time early-warning platform for a fixed research universe of 60
currently listed US companies: approximately 30 Consumer Discretionary issuers and 30 Utilities
issuers. Forecast interest coverage, free-cash-flow margin, and total-debt-to-assets, then predict
deterioration in debt-service capacity over the following four fiscal quarters.

This document is the execution plan. Each stage has dependencies, actions, deliverables, tests,
and an exit gate. A later stage should not begin until the preceding gate passes, except where
explicitly identified as safe parallel work.

## Execution status

Stages 0–18 were completed on 2026-08-02. Source counts, gate evidence, deviations, assumptions,
and limitations are recorded in [`stages_0_7_execution.md`](stages_0_7_execution.md) and
[`stages_8_12_execution.md`](stages_8_12_execution.md), and
[`stages_13_16_execution.md`](stages_13_16_execution.md), and
[`stages_17_18_execution.md`](stages_17_18_execution.md).

## End-to-end sequence

```mermaid
flowchart LR
    A["Freeze scope and contracts"] --> B["Validate public data sources"]
    B --> C["Build candidate issuer universe"]
    C --> D["Ingest raw SEC and ALFRED data"]
    D --> E["Normalize filings and fiscal quarters"]
    E --> F["Apply eligibility rules"]
    F --> G["Stratified random company selection"]
    G --> H["Create point-in-time analytical panel"]
    H --> I["Audit and freeze deterioration label"]
    I --> J["Financial and sector EDA"]
    J --> K["Engineer leakage-safe features"]
    K --> L["Freeze temporal validation design"]
    L --> M["Forecast three KPIs"]
    M --> N["Train deterioration classifiers"]
    N --> O["Select and document champion models"]
    O --> P["Materialize production pipeline"]
    P --> Q["Build and verify Tableau dashboard"]
    Q --> R["Reproduce, audit, and publish"]
```

## Stage 0 — Freeze the analytical contract

### Actions

1. Confirm the prediction unit: one company at one filing-aware decision date.
2. Confirm the four-fiscal-quarter prediction horizon.
3. Retain the candidate deterioration definition in `configs/label.yml` until its training-period
   feasibility audit.
4. Confirm the three KPI definitions and edge-case policies.
5. Confirm the fixed currently listed universe and document its survivorship limitation.
6. Define Phase 1 non-goals so additions cannot silently expand scope.
7. Assign version identifiers to the scope, universe, label, features, and source mappings.

### Deliverables

- Project charter, decision record, label specification, feature dictionary, and universe policy.
- Versioned YAML configurations validated by the command-line quality gate.

### Exit gate

- `make check` passes and no unresolved definition changes remain.

## Stage 1 — Validate free public data sources with a small proof of concept

### Source inventory

| Need | Primary source | Required point-in-time fields |
|---|---|---|
| Issuer identity and filing history | SEC Submissions API/bulk submissions | CIK, ticker, exchange, SIC, form, accession, filing date |
| As-filed financial facts | SEC Financial Statement Data Sets and XBRL APIs | accession, tag, unit, period, filing date, form, fiscal year/quarter |
| Revised macroeconomic observations | FRED/ALFRED API | observation date, real-time start/end, release/vintage date |
| Sector and industry classification | Versioned SEC SIC mapping | SIC, project sector, project industry, mapping version |

### Actions

1. Configure a real SEC User-Agent and free FRED API key locally.
2. Select 6–10 proof-of-concept issuers representing both sectors, non-calendar fiscal years,
   amendments, and differing XBRL tags. These issuers test the pipeline; they do not determine the
   final model sample.
3. Download issuer submissions, Company Facts samples, and several historical SEC bulk quarters.
4. Download one revised and one non-revised FRED series with historical availability fields.
5. Verify coverage from 2012–2025, response formats, rate limits, and reproducible source URLs.
6. Compare SEC bulk facts with individual filing metadata for several quarters.
7. Record licensing, redistribution, attribution, and caching requirements.
8. Save raw bytes unchanged and create checksum manifests for every acquisition.

### Tests

- Cached downloads are byte-identical to their recorded checksums.
- No API key appears in logs, manifests, Git, or exceptions.
- A filing fact can be traced to an accession and availability date.
- A revised macro observation can be reconstructed as known on a historical date.

### Exit gate

- All required source fields are available at usable historical depth. If a field is not viable,
  simplify the feature or KPI before scaling ingestion.

## Stage 2 — Finalize pipeline architecture and data contracts

### Actions

1. Define the Dagster asset graph and partitioning strategy before full ingestion.
2. Define DuckDB schemas and Parquet partitions for raw metadata, staged facts, fiscal quarters,
   features, labels, predictions, metrics, and Tableau exports.
3. Specify the grain, primary key, foreign keys, availability fields, and expected row counts for
   every table.
4. Define controlled reason codes for company and fact exclusions.
5. Define idempotency: rerunning the same source acquisition must not create duplicate facts.
6. Define incremental behavior for new SEC filings and new macro vintages.
7. Establish data checks for uniqueness, nulls, units, signs, ranges, reconciliation, chronology,
   and lineage.
8. Add pipeline-run metadata including configuration version and Git commit.

### Planned asset order

```text
phase1_configuration
  └── local_duckdb
      ├── sec_company_universe
      │   └── sec_as_filed_fundamentals
      │       └── normalized_company_quarters
      └── alfred_macro_vintages
              └── point_in_time_feature_table
                    ├── kpi_forecasts
                    └── deterioration_predictions
                          └── tableau_exports
```

### Exit gate

- Every downstream table has an explicit upstream source and an enforceable contract.

## Stage 3 — Construct the broad candidate-company universe

### Actions

1. Acquire the current SEC ticker/CIK list and issuer submissions metadata as of the configured
   universe date.
2. Map SEC SIC codes into Consumer Discretionary, Utilities, industry, and exclusion categories.
3. Keep domestic operating issuers on NYSE, NASDAQ, or NYSE American.
4. Exclude funds, ETFs, SPAC shells, foreign private issuers, banks, insurers, and delisted firms.
5. Deduplicate ticker changes and issuer names using CIK as the permanent entity key.
6. Create a candidate pool of approximately 100–150 issuers.
7. Store every inclusion and exclusion with a controlled reason code and evidence.

### Important restriction

Do not select companies because they are familiar, well performing, distressed, or likely to
produce an attractive result. At this stage, the candidate universe is based only on rules known
before outcome construction.

### Exit gate

- Candidate-universe reproduction produces identical CIKs from the same dated inputs and config.

## Stage 4 — Ingest full raw financial and macroeconomic history

### SEC actions

1. Download candidate-specific Company Facts histories for the complete 2012–2025 study period.
2. Extract submissions metadata for each candidate issuer from the SEC bulk submissions archive.
3. Use selected SEC Financial Statement Data Set quarters to reconcile Company Facts accession
   coverage without storing every multi-gigabyte quarterly archive.
4. Retain raw tags rather than prematurely forcing every issuer into one accounting concept.
5. Store accession, form, amendment flag, filing date, period dates, fiscal identifiers, unit,
   value, tag, and source archive.

### ALFRED actions

1. Download the configured rate, term-spread, credit-spread, unemployment, industrial-production,
   and retail-sales series.
2. Preserve historical real-time periods for revised series.
3. Store release availability separately from the observation period.

### Operational controls

- Cache source responses and prefer bulk archives.
- Run below the SEC request ceiling with bounded retry and backoff.
- Write an acquisition manifest and SHA-256 checksum.
- Never overwrite cached raw data silently.

### Exit gate

- Raw history is complete, immutable, checksummed, and traceable to public source requests.

## Stage 5 — Normalize filings and reconstruct fiscal quarters

### Actions

1. Normalize CIK, accession, dates, form types, units, scaling, and sign conventions.
2. Resolve preferred US-GAAP tags using the versioned mapping and record selected source tags.
3. Preserve company-specific tags for review rather than silently dropping them.
4. Distinguish instant balance-sheet facts from duration income/cash-flow facts.
5. Convert issuer periods into FQ1–FQ4 while retaining actual period start/end and filing dates.
6. Derive standalone FQ4 duration values as FY minus FQ1–FQ3 where necessary.
7. Never apply FQ4 subtraction to instant balance-sheet values.
8. Handle 10-Q, 10-K, and amendments without allowing a restatement before its filing date.
9. Build deterministic duplicate-resolution rules using accession and context metadata.
10. Create trailing-four-quarter values only after standalone fiscal quarters are validated.

### Quality checks

- Filing date is not earlier than period end.
- Fiscal-year duration facts reconcile to FQ1–FQ4 within documented tolerances.
- Assets, debt, revenue, and cash-flow values have valid units and plausible ranges.
- Each selected fact retains an accession and mapping-rule identifier.
- Missing and rejected facts receive reason codes.

### Exit gate

- Proof-of-concept issuers and at least a sample from every candidate industry pass manual and
  automated reconciliation.

## Stage 6 — Apply financial-history eligibility rules

### Actions

1. Calculate usable-quarter counts for each candidate.
2. Require at least 24 usable quarters and 16 consecutive quarters before an eligible prediction.
3. Calculate core-field coverage and require at least 80%.
4. Test whether interest expense is present and economically meaningful often enough to support
   interest coverage and the label.
5. Flag companies with unresolved reporting changes, extreme fiscal-calendar irregularities, or
   unusable XBRL mappings.
6. Produce an eligibility report with pass/fail status and exact reason codes.

### Exit gate

- Each sector has at least 30 eligible issuers plus an adequate reserve pool. If not, simplify a
  mapping rule or expand the candidate pool; do not lower standards for favored companies.

## Stage 7 — Select 60 companies reproducibly

### Recommended method

Use stratified random sampling after eligibility screening with the fixed project seed
`20260802`.

### Proposed strata

1. Sector: exactly 30 Consumer Discretionary and 30 Utilities issuers.
2. Industry: prevent one industry from dominating either sector.
3. Company size: use a filing-derived measure such as median total assets or revenue, avoiding a
   dependency on market data.

### Actions

1. Calculate each eligible company's industry and development-period size proxy.
2. Divide each sector into broad size tiers using only pre-holdout information.
3. Set minimum and maximum representation rules for major industries.
4. Randomly sample within strata using the versioned seed.
5. Generate a ranked reserve list using the same deterministic random draw.
6. Freeze and export the selected CIK list, selection probabilities, strata, seed, and reserve
   ordering.

### Anti-selection-bias rule

Do not resample because the chosen companies yield too few deterioration events or weak model
performance. If the label is statistically infeasible, expand the universe using the frozen
reserve ordering or increase the total company count transparently; do not search random seeds.

### Exit gate

- Re-running selection from the eligible pool produces the identical 60-company universe.

## Stage 8 — Create the point-in-time company-quarter panel

### Pre-model company certification

Stage 8 must certify the complete company population before label construction or modeling. A
company must support all three consistently defined KPIs; KPI-specific participation is not
permitted in Phase 1. Apply the versioned rules in `configs/analytical_panel.yml`.

### Actions

1. Establish filing-aware decision dates for each selected company.
2. At each decision date, use only facts with `available_at <= decision_at`.
3. Join the latest historically available macro vintage using the same rule.
4. Construct standalone-quarter and TTM accounting measures.
5. Calculate the three core KPIs and secondary financial ratios.
6. Calculate sector and industry benchmarks using information available at that date.
7. Preserve missingness indicators, mapping confidence, and fact lineage.
8. Create a unique company-decision-date key and reject duplicates.
9. Audit each KPI for at least 24 observed quarters, 16 consecutive quarters, and 80% coverage for
   every company, together with valid lineage and resolved essential mappings.
10. Produce a machine-readable certification table containing every company-rule result and the
    underlying counts, dates, coverage rates, and reason codes.
11. Replace any failing company with the next same-sector issuer in the frozen reserve order and
    apply the identical certification rules. Do not inspect labels or model results when replacing.
12. If the reserve list cannot restore 30 certified companies per sector, stop and propose a
    transparent candidate-pool expansion; do not weaken a data-quality threshold.
13. Freeze a new universe version only if replacements occur, record a before/after manifest, and
    rematerialize the local financial store to contain only the certified final 60.

### Exit gate

- Automated leakage tests prove that no filing, restatement, or macro vintage enters early.
- All 60 companies pass every KPI and lineage gate, the certification report is complete, and any
  replacement is reproducible from the frozen same-sector reserve order.

## Stage 9 — Construct, audit, and freeze the deterioration label

### Actions

1. Generate the candidate four-quarter-forward interest-coverage deterioration label.
2. Collapse overlapping positive rows into distinct deterioration episodes using the configured
   cooldown policy.
3. Examine positive rows, distinct events, and affected companies by sector, size, year, and
   economic environment using development dates only.
4. Review negative EBIT, small denominators, already-distressed issuers, and missing future
   quarters.
5. Compare a small prespecified threshold sensitivity grid for economic plausibility—not model
   performance.
6. Confirm that the planned final holdout has enough distinct events to be interpretable.
7. Freeze the label version and document any change from the candidate definition.

### Decision rule

If events are too sparse, first expand the universe through the frozen reserve list or lengthen
the development period. Do not replace deterioration with bankruptcy, tune thresholds against
test-model performance, or resample companies until the outcome looks favorable.

### Exit gate

- The label has a frozen formula and a documented population of distinct events.

## Stage 10 — Conduct financial, sector, and time-series EDA

### Financial EDA

- Revenue, operating income, cash flow, debt, asset, coverage, margin, and leverage distributions.
- Missingness, outliers, signs, denominator problems, and reporting changes.
- Current levels, annual changes, rolling trends, and sector-relative positions.
- Company examples that explain how deterioration develops economically.

### Sector EDA

- Cyclical versus defensive behavior.
- Industry composition and company-size balance.
- Sector medians, dispersion, and deterioration prevalence.
- Macro sensitivity and different meanings of structurally high utility leverage.

### Time-series EDA

- Persistence, autocorrelation, trend, structural breaks, distributions, and signal-to-noise ratio.
- Missing/irregular observations and forecastability by KPI and sector.
- Whether transformations, clipping, differencing, or local trends are justified.

### Exit gate

- Every preprocessing and model choice has a documented empirical and financial rationale.

## Stage 11 — Build leakage-safe preprocessing and features

### Actions

1. Separate raw facts, accounting transformations, model features, and display-only values.
2. Define missingness handling by economic meaning; do not globally impute all ratios the same way.
3. Fit imputation, clipping, scaling, and feature selection inside each training fold.
4. Create current, lagged, year-over-year, rolling-trend, volatility, and peer-relative features.
5. Restrict correlated macro inputs or use a small prespecified set.
6. Add forecast summaries only after forecasts are generated without seeing future outcomes.
7. Encode sector and a limited set of economically justified interactions.
8. Create model-ready matrices and human-readable reason-code mappings from one feature registry.

### Exit gate

- Feature tests cover formulas, availability, ranges, deterministic output, and fold isolation.

## Stage 12 — Freeze temporal splits and evaluation procedures

### Actions

1. Define expanding-window training and validation folds with at least 24 training quarters.
2. Choose the final holdout boundary using coverage and event counts, before model comparison.
3. Account for the four-quarter label horizon with an embargo or label-availability cutoff between
   training and validation.
4. Fit preprocessing, feature selection, and hyperparameter tuning entirely within each fold.
5. Define forecasting metrics: MAE, RMSE, interval coverage, and sector stability.
6. Define classification metrics: PR-AUC, recall, precision, lift, Brier score, calibration, and
   alert volume.
7. Define episode-level and sector-level reporting for overlapping outcomes.
8. Freeze the metric hierarchy and model-selection rules.

### Exit gate

- A model cannot access the final holdout or future labels during development.

## Stage 13 — Forecast the three financial KPIs

### Model sequence for each KPI

1. Random walk.
2. Random walk with drift where exploratory evidence supports it.
3. Local-level state-space model.
4. Local-linear-trend state-space model.
5. Regression state-space/DLM with a small justified macro predictor set.

### Actions

1. Decide whether models are fit per company, pooled by sector, or through a constrained hybrid
   based on available history and convergence diagnostics.
2. Produce one- and four-quarter forecasts and intervals through rolling origins.
3. Record convergence, parameter stability, residual diagnostics, missing-data behavior, and
   interval coverage.
4. Compare models by KPI, sector, horizon, and low/high-signal series.
5. Select the simplest defensible forecast model for each KPI/scenario.
6. Generate leakage-safe forecast summaries for classifier inputs.

### Exit gate

- Advanced forecasts must beat or meaningfully complement naïve baselines; otherwise retain the
  simpler baseline and document why.

## Stage 14 — Train deterioration models incrementally

### Model sequence

1. Regularized logistic regression as the interpretable baseline.
2. Constrained gradient-boosted trees as the nonlinear challenger.

### Feature-increment experiments

1. Current fundamentals only.
2. Add historical trends and peer-relative features.
3. Add forecasted interest coverage.
4. Add all three KPI forecast summaries.
5. Add macro variables and limited sector interactions.

### Actions

1. Tune class weights, regularization, tree depth, learning rate, and number of estimators inside
   temporal validation.
2. Avoid generic oversampling that breaks temporal or company structure.
3. Produce out-of-fold probabilities for every development-period evaluation row.
4. Evaluate calibration before choosing alert thresholds.
5. Select operating thresholds using analyst-review capacity and missed-event cost.
6. Report errors and stability by sector, time period, and size tier.
7. Produce coefficients, SHAP values, and financially understandable local reason codes.

### Exit gate

- Results show whether nonlinear modeling and forecast features add reliable out-of-time value.

## Stage 15 — Select champion and challenger models

### Decision hierarchy

1. Temporal validity and absence of leakage.
2. Calibration and stability across folds/sectors.
3. Recall, PR-AUC, lift, and alert-volume usefulness.
4. Forecast error and interval coverage for KPI models.
5. Interpretability and reason-code stability.
6. Complexity, convergence, and reproducibility.

The highest ROC-AUC model is not automatically selected. Maintain logistic regression and naïve
forecasts as permanent challengers even if more complex models win.

### Deliverables

- Experiment register, model-selection table, final test report, model card, and limitation log.

### Exit gate

- Champion decisions are reproducible from frozen predictions and documented selection rules.

## Stage 16 — Complete the production-style pipeline

### Actions

1. Replace placeholder Dagster assets with tested implementations.
2. Partition raw and staged data by source period; partition predictions by decision period.
3. Support a full historical rebuild and a smaller incremental refresh.
4. Add asset checks for source freshness, row counts, uniqueness, availability, reconciliation,
   feature ranges, label completion, and prediction validity.
5. Log pipeline runs, configuration versions, Git commits, timings, and failures.
6. Persist model artifacts and experiment metadata outside Git.
7. Add CI tests using small deterministic fixtures; keep network tests optional and isolated.
8. Generate a data-lineage diagram from the final asset graph.

### Exit gate

- A clean checkout can reproduce the tested local pipeline by following the README.

## Stage 17 — Build and verify the Tableau dashboard

### Pages

1. Portfolio overview: monitored companies, alert counts, risk distribution, and sector comparison.
2. Watchlist: probability, change in risk, KPI outlook, peer position, and primary drivers.
3. Company detail: historical statements/ratios, three KPI forecasts with intervals, peer
   comparison, and risk history.
4. Model performance: out-of-fold metrics, calibration, lift, sector stability, and limitations.

### Actions

1. Generate the four configured Tableau-ready exports from tested marts.
2. Ensure backtest views use out-of-fold predictions only.
3. Reconcile every Tableau KPI to its Python/DuckDB source calculation.
4. Add filters for sector, industry, company, period, and alert status.
5. Clearly label synthetic examples, missing values, forecast uncertainty, and model limitations.
6. Test dashboard usability, data freshness, and public-data safety.

### Exit gate

- Dashboard totals and sampled company details exactly match tested analytical outputs.

## Stage 18 — Reproduce, document, and publish Phase 1

### Actions

1. Rebuild the project from a clean environment using the locked dependencies.
2. Run all unit, integration, data-contract, leakage, and pipeline tests.
3. Recreate the universe, data manifests, analytical panel, model results, and Tableau extracts.
4. Complete the data card, model card, architecture diagram, assumptions, and limitations.
5. Add a concise resume description and technical case-study summary.
6. Confirm that Git contains no credentials, prohibited source data, machine-specific paths, or
   untracked business logic.
7. Tag the reproducible Phase 1 release.

### Final completion gate

Another user can follow the public instructions and reproduce the claimed analysis from the
documented public sources. All reported performance derives from frozen temporal evaluation, and
all claims remain limited to the selected currently listed company universe.

## Cross-cutting issue register

The following issues must be tracked throughout the relevant stages rather than addressed only at
the end:

| Issue | Primary control |
|---|---|
| Different fiscal year-ends | Preserve actual dates plus issuer-relative FQ1–FQ4 |
| Restatements and amendments | Accession-aware `available_at` logic |
| XBRL tag inconsistency | Versioned mapping, overrides, and fact-level lineage |
| Survivorship bias | Limit claims to the fixed current-company universe |
| Sparse deterioration events | Event audit; expand via frozen reserve order if necessary |
| Overlapping four-quarter labels | Episode reporting, embargo, and sensitivity analysis |
| Sector accounting differences | Sector-relative features and sector-specific reporting |
| Small effective sample | Constrained models and company/episode-aware uncertainty |
| Missing values | Economically specific handling fitted inside training folds |
| Model leakage | Point-in-time joins and fold-isolated transformations |
| Dashboard leakage | Out-of-fold backtest exports only |
| Data licensing | Public-source register; do not commit restricted raw data |
| Reproducibility | Locked environment, manifests, configs, tests, and clean rebuild |

## Confirmed Stage 7 decisions

1. Use median total assets as the primary company-size proxy, with revenue as a tie-breaker.
2. Use broad industry and three size tiers for stratified random selection.
3. Permit expansion up to 80 companies only if the frozen event-feasibility gate fails, using the
   predetermined reserve order rather than a new random seed.
