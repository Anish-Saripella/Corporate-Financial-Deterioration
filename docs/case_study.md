# Case Study: Corporate Financial Deterioration Early Warning

## Business question

Can public financial data identify active companies whose capacity to cover interest expense is
likely to deteriorate over the next four fiscal quarters, early enough to prioritize analyst
review? The project treats this as a ranked early-warning problem rather than bankruptcy prediction.

## Data and analytical design

The final study covers 117 active US companies: 75 Consumer Discretionary issuers and all 42
eligible Utilities available under the project rules. Companies were classified from reviewed SEC
SIC mappings and business descriptions. Eligibility was applied before seeded random sampling, and
no synthetic or proprietary data was used.

SEC facts were normalized across XBRL concepts and issuer fiscal calendars. Filing and amendment
dates controlled when a value became available; FRED/ALFRED variables were joined using historical
vintages. The four-quarter outcome was positive when future interest coverage fell below 1.5x and
declined by at least 40% from its current value within four consecutive quarters.

Financial ratios, peer positions, trends, forecast summaries, and selected macroeconomic variables
entered expanding-window validation. Preprocessing, feature screening, calibration, and threshold
selection were fitted using training history only. Adjacent quarterly outcomes overlap, so
company-clustered uncertainty complements row-level metrics.

## Model development

Phase 1 established the reproducible benchmark and achieved 0.397 PR-AUC on its 2023-and-later
holdout. Phase 2 expanded the population, strengthened the feature and interpretability pipeline,
and initially compared partially pooled logistic regression with constrained boosting.

A controlled optimization then compared regularized logistic regression, random forests,
histogram gradient boosting, support-vector classification, pooled and sector-specific XGBoost,
and several static and time-adaptive ensembles. Selection used development folds only. The final
60% pooled / 40% sector-specific XGBoost blend was frozen before the sealed out-of-time test.

## Final evidence

The selected ensemble achieved 0.760 development ROC-AUC and 0.462 development PR-AUC. At the
common 80%-recall development policy, it reduced the alert rate from 57.6% for the initial Phase 2
model to 51.3%.

On the sealed late-2024 test, covering 178 observations and 28 deterioration events, the ensemble
achieved:

- 0.841 ROC-AUC;
- 0.494 PR-AUC;
- 85.7% recall;
- 26.4% precision; and
- a 51.1% alert rate.

An 85.7% recall means the policy identified 24 of the 28 observed deterioration events. A 51.1%
alert rate means roughly half of the company-quarter observations were sent for review; it does not
mean half were classified correctly. The workload is meaningful but consistent with the stated
preference to miss fewer deteriorations.

## Interpretation and limits

The sealed result exceeded the 0.80 ROC-AUC objective and improved on the development comparison,
but it is one out-of-time period rather than proof of permanent performance. Company-clustered
uncertainty is wide, Utility recall is based on seven events, and the active-company-only sample
creates survivorship bias. Results cover two sectors and cannot yet be generalized to the broader
credit market.

The practical output is a transparent screening tool that flags companies for further review and
helps analysts identify potential interest-coverage problems more efficiently. The final
[combined report](../reports/publication/Corporate_Financial_Deterioration_Combined_Phase1_Phase2_Research_Report.pdf)
contains the complete methodology, case reviews, and limitations; the
[optimization supplement](../reports/publication/Phase2_Model_Optimization_and_Out_of_Time_Results.md)
provides the concise model comparison.
