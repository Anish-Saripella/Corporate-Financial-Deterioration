# Financial Deterioration Screening

## Portfolio case study

### Business problem

Financial analysts cannot perform a full credit review of every public company every quarter. This
project builds a first-pass screening system that ranks companies for manual review when their
ability to cover interest expense may deteriorate. It is not a bankruptcy model, credit rating, or
investment recommendation.

The operating preference is explicit: missing a genuine deterioration is more costly than reviewing
a false alert. The model must therefore attain at least 80% recall separately in Consumer
Discretionary and Utilities. Among thresholds that satisfy recall, it selects the one producing the
smallest analyst queue.

### Data and sample

The point-in-time pipeline combines SEC EDGAR financial statements and filing metadata with
FRED/ALFRED macroeconomic data. The frozen population contains 117 currently active US operating
companies:

- 75 Consumer Discretionary issuers.
- 42 Utility issuers.
- Selection date: August 2, 2026.
- Financial-history cutoff: December 31, 2025.
- No delisted companies and no synthetic data.

Eligibility is applied before randomized selection. Companies need reliable interest-coverage and
asset histories, but occasional gaps in optional predictors are permitted. The sample uses seeded,
stratified random selection without replacement. Equal aggregate sector weights prevent the larger
Consumer sample from dominating model training.

Grocery-dominant discount retailers are excluded from Consumer Discretionary because the product
mix is staples-oriented. Sector mapping uses SEC SIC classifications and reviewed business
descriptions rather than relying on store format or company name.

### Point-in-time pipeline

The most important engineering requirement is reproducing what an analyst could have known at each
historical decision date. Fiscal period end is not assumed to be publication date. The pipeline:

1. Retrieves and checksums public SEC and FRED source responses.
2. Normalizes XBRL concepts while retaining filing, amendment, fiscal-period, and availability
   lineage.
3. Constructs quarterly and trailing-twelve-month financial ratios.
4. Joins only macroeconomic vintages observable at the decision date.
5. Creates an outcome only when every required future fiscal quarter is consecutive and observed.
6. Fits preprocessing, imputation, feature selection, calibration, and thresholds using training
   evidence only.

### Modeling design

The primary model is a regularized partially pooled logistic classifier. It learns a shared
relationship across the two sectors while permitting a small number of Utility-specific deviations.
A pooled logistic model is the benchmark, and constrained gradient boosting is the nonlinear
challenger.

The four-quarter primary outcome is positive when future interest coverage:

- Falls below 1.5x; and
- Declines at least 40% from the current value within four consecutive future fiscal quarters.

The two-quarter sensitivity uses the identical financial rule over two consecutive quarters. It is
not allowed to replace the primary simply because it produces a better score.

### Leakage controls

The system uses expanding-window temporal validation. For each fold, the training period precedes
the validation period. A row enters training only if its complete outcome was already observable
before validation began.

Predictor imputation, missing-value indicators, correlation screening, permutation importance,
hyperparameter selection, and calibration are fitted inside training history. The outer validation
period is not used to choose features or tune the model.

Stable selected variables include:

- Current interest coverage.
- Interest-coverage trend and sector percentile.
- Free-cash-flow-margin sector percentile.
- Operating margin.
- Revenue growth.
- Cash-flow conversion.

Refinancing gap/assets was selected in one early fold, but it was unstable and absent from the
latest-fold recommendation. Filing delay is excluded from the classifier; it remains only a
data-quality and analyst case-review field.

### Main four-quarter result

On the complete development out-of-fold comparison, constrained boosting achieved 0.412 PR-AUC
versus 0.379 for the partially pooled logistic primary. The challenger ranked events better, while
the primary remained easier to explain. This is presented as a real interpretability-performance
tradeoff.

The original four-quarter development policy attained approximately 80% recall in both sectors but
required a large review queue. This demonstrated that the recall target was feasible, not that the
system was ready for autonomous use.

### Two-quarter versus four-quarter experiment

The scientific comparison used the same companies, same 397 calibrated validation
company-quarters, same calendar folds, and separate fold-local model selection for each outcome.

| Metric | Four-quarter primary | Two-quarter sensitivity |
|---|---:|---:|
| Event prevalence | 19.4% | 12.1% |
| PR-AUC | 0.262 | 0.171 |
| Overall recall | 80.5% | 81.3% |
| Consumer recall | 80.0% | 80.0% |
| Utility recall | 81.8% | 84.6% |
| Precision | 23.2% | 16.7% |
| Alert rate | 67.3% | 58.9% |
| Brier score | 0.159 | 0.106 |
| Expected calibration error | 0.069 | 0.040 |
| Median warning lead | 2.0 quarters | 1.0 quarter |

The two-quarter outcome added 318 mature company-quarters to the complete underlying label pool,
but it produced fewer positive rows because a deterioration had less time to occur.

Company-clustered bootstrap results for two quarters minus four quarters showed:

- Alert rate: −8.3 percentage points, 95% interval [−12.3, −4.3].
- Precision: −6.6 percentage points, 95% interval [−11.1, −2.7].
- PR-AUC: −0.090, 95% interval [−0.195, −0.013].
- Brier score: −0.053, 95% interval [−0.072, −0.033].

The shorter horizon therefore produced a statistically credible reduction in workload, but also a
credible decline in precision. Its lower Brier score partly reflects lower event prevalence and
does not offset the weaker ranking. The company-clustered PR-AUC interval excludes zero, supporting
a material ranking decline in this development comparison.

### Three company decisions

#### True positive: Designer Brands (DBI)

At the June 4, 2024 decision point, the model assigned 69.3% risk against a 10.5% Consumer
threshold. Interest coverage was 6.01x, free-cash-flow margin was 6.4%, and operating margin was
5.5%. Rising leverage was the principal monitored explanation. Coverage subsequently reached
0.93x three quarters later, satisfying the deterioration rule.

The alert would have been useful because it directed attention to worsening balance-sheet pressure
before the qualifying coverage outcome.

#### False positive: Under Armour (UAA)

At May 29, 2024, the model assigned 92.1% risk. Interest coverage was already −7.49x,
free-cash-flow margin −27.8%, and operating margin −3.8%. These conditions understandably resembled
financial stress. However, the future path did not meet both parts of the label relative to its
already negative starting point.

This was statistically a false positive, but it could still justify a precautionary analyst review.
It also illustrates a label limitation: companies already in a deeply negative coverage state can
behave differently from companies deteriorating from positive coverage.

#### Missed deterioration: NRG Energy (NRG)

At February 28, 2024, NRG scored 12.1%, narrowly below the 12.3% Utility threshold. Current interest
coverage was a relatively healthy 6.89x, free-cash-flow margin 0.8%, and operating margin 12.5%. No
monitored ratio was extreme enough to generate a standard explanation code. Coverage later fell to
−1.48x, with the qualifying breach occurring one quarter later.

The miss shows the limit of historical financial predictors: a future decline may not be visible in
currently reported ratios. It also supports retaining manual sector knowledge and monitoring
external events rather than treating the probability as a complete credit opinion.

### Conclusion

The two-quarter model should not replace the four-quarter primary outcome. It reduces the review
queue but ranks a narrower set of near-term events less effectively, lowers precision, and shortens
warning lead time. The most defensible use is a secondary near-term flag alongside the four-quarter
medium-term screen.

### Limitations and next steps

- The sample contains only active companies, creating survivorship bias.
- Only two sectors are included; Utility evidence is more limited.
- Adjacent quarterly labels overlap and are correlated.
- The post-2025 final test cannot be opened until four-quarter outcomes mature.
- Analyst capacity should be measured before operationalizing a roughly 60%–70% alert rate.
- Future probabilities should be recalibrated on newly matured outcomes before deployment.

### Skills demonstrated

Financial-statement analysis, SEC/FRED data engineering, point-in-time joins, temporal validation,
missing-data methods, imbalanced classification, leakage-safe feature selection, calibration,
interpretability, company-clustered uncertainty, threshold optimization, model governance,
automated testing, and translation of statistical evidence into a financial review process.
