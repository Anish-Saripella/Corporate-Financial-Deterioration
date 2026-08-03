# Time-Aware Validation Plan

## Forecasting

- Rolling-origin or expanding-window evaluation.
- One- and four-quarter horizons.
- Random walk and random walk with drift as required baselines.
- State-space challengers evaluated using MAE, RMSE, interval coverage, and sector stability.

## Deterioration classification

- Three annual expanding-window folds with at least 24 training quarters.
- Preprocessing, feature selection, and tuning fit inside each fold.
- Labels whose four-quarter outcome window is not complete by a fold origin are embargoed.
- The final out-of-time holdout begins 2023-01-01 and was frozen after a development-only event
  audit, before model fitting or comparison.
- Regularized logistic regression and constrained gradient boosting.
- PR-AUC, recall, precision, top-decile lift, Brier score, calibration, and alert volume.
- Performance reported by sector and time period.

## Overlapping outcomes

Adjacent company-quarter rows share future windows. Evaluation will report distinct deterioration
episodes, company-level bootstrap uncertainty where feasible, and sensitivity to less-frequent
decision dates. Row count will never be presented as the number of independent events.

## Model-increment tests

1. Current fundamentals.
2. Current fundamentals plus historical trends.
3. Add forecasted interest coverage.
4. Add all three KPI forecast summaries.

These comparisons determine whether forecasting adds value; the advanced model is not assumed to
win.

The primary classifier selection metric is PR-AUC. Calibration, sector stability, temporal
stability, interpretability, and simplicity are evaluated in that order after primary predictive
performance. The locked holdout is unavailable during model development.
