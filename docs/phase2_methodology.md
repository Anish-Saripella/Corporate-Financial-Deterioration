# Phase 2 Model Improvement, Interpretability, and Analytical Methodology

## Purpose and level of analysis

Phase 2 remains an applied corporate-finance and data-science research project. It adds stronger
validation and interpretation without requiring methods that obscure the financial reasoning. The
main question remains:

> Given information available when a company filed, can we rank active public companies by the
> probability that debt-service capacity will deteriorate over the next four fiscal quarters?

The output is an early-warning score. It is not a default probability, credit rating, causal model,
or trading recommendation.

## Confirmed scope

- Population: US operating companies active on August 2, 2026.
- Exchanges: NYSE, NASDAQ, and NYSE American.
- Sectors: Consumer Discretionary and Utilities.
- Final sample: 75 Consumer Discretionary and 42 Utility issuers supported by reliable
  interest-coverage histories.
- Financial-history cutoff: December 31, 2025.
- Sources: SEC EDGAR and FRED/ALFRED.
- Delisted companies: excluded.
- Sampling: seeded stratified random sampling without replacement, inherited from Phase 1.

The active-company restriction creates survivorship bias. Phase 2 can make stronger statements
about currently active issuers than Phase 1 because it has more companies, but it still cannot
represent bankrupt or delisted firms.

## Pipeline and information flow

1. `build-phase2-eligibility` downloads the SEC submissions archive and Company Facts for every
   mapped active candidate. The full eligibility audit occurs before final sampling.
2. `freeze-phase2-universe` uses seed `20260802` to select 75 Consumer and 42 Utility issuers across
   industry and three asset-size tiers. Seven Consumer reserves are frozen; all eligible Utilities
   are used.
3. `build-phase2-panel` joins filing-time accounting facts to point-in-time macro vintages. The old
   all-KPI certification remains an auditable quality tier, while actual modeling eligibility is
   evaluated at the company-quarter level.
4. Optional predictor gaps are permitted. Imputation, missingness indicators, clipping, and scaling
   are fit inside each temporal training fold. Labels require four consecutive future quarters.
5. `run-phase2-development-models` constructs the frozen benchmark label and new backward-looking
   features, then runs nested expanding-window validation.
6. `analyze-phase2-development` produces statistical, operational, episode, calibration, and
   uncertainty tables from real out-of-fold predictions.
7. `build-phase2-governance` materializes non-causal company reason codes, calibration, recall-first
   sector thresholds, drift monitoring, and the model/data card.
8. `write-phase2-research-report` converts the generated evidence into an accessible technical
   report intended for a recent master's-level reader.
9. A future test period remains unset. It may be opened exactly once only after the design, model,
   calibration method, and alert policy are frozen and enough future labels mature.

No command creates synthetic analytical data.

## Outcome definitions

### Benchmark outcome

The Phase 1 benchmark remains primary. A company-quarter is positive when, during the next four
fiscal quarters:

1. minimum trailing-twelve-month interest coverage is below 1.5 times; and
2. coverage has declined by at least 40% relative to the decision quarter.

Interest coverage is operating income divided by positive interest expense. A lower value means
less earnings protection for scheduled interest payments. This label measures deterioration in
debt-service capacity—not bankruptcy.

### Sensitivity outcomes

The code preregisters two-, four-, and six-quarter horizons and coverage thresholds of 1.0, 1.5,
and 2.0. It also evaluates a simple multi-KPI outcome requiring two of:

- benchmark debt-service weakness;
- negative free-cash-flow margin; and
- at least a 0.10 absolute increase in debt/assets.

These alternatives test whether findings depend on one reasonable definition. They are not
searched after seeing model scores, and the label with the best PR-AUC is not automatically chosen.

## Financial predictors

Phase 2 begins with a limited, financially understandable candidate list. It includes:

- Core condition: interest coverage, free-cash-flow margin, debt/assets, operating margin, current
  ratio, and cash/assets.
- Financing: refinancing gap/assets remains a candidate but must pass feature selection.
- Liquidity and cash flow: working capital/assets, capital expenditure/revenue, and operating cash
  flow relative to operating earnings.
- Operations: revenue growth, asset turnover, and net-income margin.
- Persistence: year-over-year changes, four-quarter volatility, and four-quarter trends.
- Peer context: sector percentile and distance from the same-quarter sector median.
- Data quality: filing delay and XBRL quality fields are retained only for monitoring and case
  review. They are never treated as direct evidence of deterioration or used by the classifier.

Missing or undefined ratios stay missing until the model’s temporal training fold. Median
imputation, clipping, scaling, and categorical encoding are learned within that fold, preventing
future validation data from influencing preprocessing.

## Feature selection

Feature selection occurs separately inside every outer training fold; outer validation outcomes
are never inspected. The procedure applies an economic whitelist, removes features with more than
60% training missingness or no variation, removes near-duplicates above 0.92 absolute Spearman
correlation, and measures permutation PR-AUC loss five times in each inner time window. A feature
must improve ranking in at least 67% of permutations, except current interest coverage, which is
required because it defines the research outcome. Each fold retains between 8 and 18 predictors.

This establishes stable development-period predictive relevance, not causal importance or a
population p-value. The evidence and removal reason for every candidate are saved in
`phase2_feature_selection_evidence.csv` and `phase2_feature_selection_stability.csv`.

## Nested expanding-window validation

Random train/test splitting is inappropriate because it lets future economic regimes inform past
predictions. Each outer fold trains on earlier quarters and validates on a later four-quarter
window. A label enters training only when its entire future outcome window was known before the
validation origin. This creates an embargo for overlapping labels.

Within each outer training sample, smaller expanding windows choose logistic regularization and
the positive-class weight. This is *nested validation*: the outer validation period evaluates a
choice made using only earlier inner periods.

Quarterly rows from the same company remain correlated. Final uncertainty therefore resamples
whole issuers, not individual rows.

## Model architectures

### Pooled regularized logistic regression

All companies share coefficients, with sector and industry indicators. Logistic regression is the
most readable challenger: a positive standardized coefficient increases log-odds, holding other
modeled variables constant. L2 regularization shrinks unstable coefficients toward zero.

### Partially pooled sector interactions

The model retains common coefficients and adds a small preregistered set of Utility deviations. A
deviation is retained only when repeated development data support it; regularization shrinks weak
sector differences. This borrows information across sectors while allowing economically plausible
differences in leverage, coverage, refinancing, capital expenditure, and cash flow.

Fully separate and discrete-time hazard models were removed from Phase 2. The approved comparison is
the partially pooled primary model, pooled logistic benchmark, and constrained pooled gradient
boosting challenger. Forecasts are evaluated separately and are not primary classifier inputs.

## Calibration

Ranking and calibration are separate properties. PR-AUC asks whether events rank above non-events;
calibration asks whether a predicted 30% risk occurs approximately 30% of the time.

Phase 2 compares:

- no recalibration;
- intercept-only recalibration, which corrects the overall event-rate shift;
- Platt scaling, which adjusts the slope and intercept of log-odds; and
- isotonic regression, a flexible monotonic mapping.

Each fold’s calibrator is trained only on out-of-fold predictions from earlier periods. Both pooled
and sector-specific versions are tested. Brier decomposition separates reliability, resolution,
and outcome uncertainty.

## Forecast uncertainty

Phase 1 four-quarter intervals sometimes covered fewer observations than their nominal 95% level.
Phase 2 learns empirical absolute-residual widths from completed development forecasts by KPI,
sector, and horizon. A subgroup with fewer than 30 observations falls back to the pooled KPI/horizon
width. This conformal-style approach does not assume normally distributed forecast errors.

## Alert policy and analyst usefulness

Probability estimation and analyst workload are separate decisions. Because missed deteriorations
are considered more costly than extra manual reviews, Phase 2 first requires a minimum recall in
each sector and then selects the least-work threshold that meets it. Consumer and Utility thresholds
may differ. The registered target is 80% recall within each sector, with 60%, 70%, and 90% shown as
sensitivity scenarios. Phase 2 also reports:

- precision, event capture, and lift when reviewing the top 5%, 10%, and 20% of scores;
- distinct episodes captured, so overlapping quarterly labels do not masquerade as independent
  successes;
- sector-specific threshold results and total analyst workload;
- net analytical value under stated costs for a missed event, unnecessary review, and correctly
  identified event; and
- comparison with reviewing none, reviewing everyone, or random screening.

The default cost units are scenarios, not dollars. A missed event costs five units and an
unnecessary review costs one; results must show sensitivity to those assumptions.

## Company explanations

Reason codes connect a score to observed ratios, recent changes, sector position, macro conditions,
forecast uncertainty, and source quality. The reference percentiles come from development data.
Reasons describe predictive associations. They do not prove that a feature caused deterioration or
that management should mechanically change it.

## Monitoring and governance

The preregistered monitor covers source freshness, issuer mix, missingness, feature PSI, matured
event rate, ranking, calibration error, and alert volume. PSI at 0.10 triggers investigation and
0.25 triggers escalation. Drift alone does not authorize retraining. Calibration failure suggests
recalibration on matured labels; ranking failure requires reconsidering features and model choice.

Versioned artifacts include the universe, replacement audit, source manifests, point-in-time panel,
feature registry, label sensitivity table, temporal folds, nested selections, raw and calibrated
OOF predictions, threshold analysis, explanations, monitoring results, and final test report.

## Current scientific limitation

The 2023-and-later Phase 1 holdout has already been evaluated. Phase 2 may use it in development
backtests, but cannot call it untouched evidence. Because financial history ends in 2025, no honest
new final test performance can yet be reported. Phase 2 remains development-only until a later
prospective window accumulates complete four-quarter outcomes.
