# Resume and Interview Summary

## Resume project entry

**Corporate Financial Deterioration Early-Warning Platform — Python, SQL, DuckDB, Dagster,
scikit-learn, XGBoost, statsmodels**

- Engineered a reproducible, point-in-time SEC/FRED pipeline for 117 active public companies across
  Consumer Discretionary and Utilities, standardizing fiscal quarters and enforcing filing-date,
  source-lineage, continuity, and leakage controls without synthetic or proprietary data.
- Forecast interest coverage, free-cash-flow margin, and debt-to-assets; converted forecast level,
  change, and uncertainty into leakage-safe risk features evaluated with expanding-window temporal
  validation.
- Compared interpretable, tree-based, support-vector, sector-specific, and ensemble classifiers;
  froze a 60% pooled / 40% sector-specific XGBoost blend before a one-time out-of-time evaluation.
- Achieved 0.841 ROC-AUC, 0.494 PR-AUC, and 85.7% recall on a sealed late-2024 test containing 178
  observations and 28 deterioration events, while reducing the comparable development alert rate
  from 57.6% to 51.3% at the 80%-recall policy.
- Delivered tested Python modules, DuckDB/Parquet analytical storage, machine-readable evidence,
  documented limitations, and publication-ready research reports.

## Interview narrative

Start with the business problem: analysts need a repeatable way to prioritize companies for review
when debt-service capacity may weaken. The target is therefore a defined decline in future interest
coverage, not bankruptcy or default. The model is an additional screening tool; its probability and
supporting financial signals help analysts decide where to investigate further.

Then explain the data design. SEC filing dates prevent look-ahead leakage, fiscal-quarter
normalization makes issuers comparable, and FRED/ALFRED vintages preserve what was historically
available. The sample is restricted to active issuers and two sectors, so survivorship bias and
limited sector generalization are disclosed rather than hidden.

For modeling, regularized logistic regression provides an interpretable benchmark, while random
forests, histogram gradient boosting, support-vector models, and XGBoost test whether nonlinear
thresholds or sector-specific relationships improve ranking. Candidate models and static or
time-adaptive ensembles were compared only in development. A fixed XGBoost blend and thresholds
were then frozen before the sealed late-2024 test.

Use the metrics deliberately. ROC-AUC summarizes ranking across thresholds; PR-AUC is important
because deterioration events are the minority class; recall measures how many events are captured;
and alert rate translates the threshold into analyst workload. The sealed test exceeded the 0.80
ROC-AUC target and captured 85.7% of events, but the 51.1% alert rate remains substantial and the
Utility result is based on only seven events. That combination supports a useful review-prioritizing
tool while keeping the statistical limitations visible.
