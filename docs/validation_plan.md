# Time-Aware Validation Plan

## Forecasting

- Rolling-origin or expanding-window evaluation.
- One- and four-quarter horizons.
- Random walk and random walk with drift as required baselines.
- State-space challengers evaluated using MAE, RMSE, interval coverage, and sector stability.

## Deterioration classification

- Expanding-window folds with at least 24 training quarters.
- Preprocessing, feature selection, and tuning fit inside each fold.
- Final out-of-time holdout chosen after an event-count audit and frozen before comparison.
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
