# Resume and Interview Summary

## Resume project entry

**Corporate Financial Deterioration Early-Warning Platform — Python, SQL, DuckDB, Dagster,
scikit-learn, statsmodels, Tableau**

- Engineered a reproducible point-in-time SEC/FRED pipeline for 60 public companies and 3,150
  certified fiscal-quarter observations, standardizing non-calendar filings and enforcing
  availability-date, lineage, KPI-coverage, and leakage controls.
- Forecast interest coverage, free-cash-flow margin, and debt-to-assets with random-walk, drift,
  and state-space models; converted forecast level, change, and uncertainty into leakage-safe risk
  features evaluated through expanding-window backtests.
- Built a champion–challenger framework comparing regularized logistic regression and calibrated
  gradient-boosted trees; the frozen champion achieved 0.397 PR-AUC, 0.563 recall, and 1.97x
  top-decile lift on an untouched 2023+ holdout.
- Delivered a Dagster asset graph, DuckDB/Parquet feature store, automated quality gates, model and
  data cards, and a reconciled four-page Tableau dashboard for sector monitoring and analyst
  watchlist review.

## Interview narrative

The project demonstrates the full lifecycle rather than a collection of algorithms. Start with the
business framing: deterioration in debt-service capacity is measurable and decision-relevant,
whereas bankruptcy is too rare and poorly labeled for this public-data scope. Explain how filing
dates prevent look-ahead leakage, why two sectors test cyclical differences, and why delisted-company
exclusion is disclosed as survivorship bias.

Then describe model choice. Random walks establish whether state-space complexity adds value;
logistic regression provides an interpretable baseline; constrained boosted trees capture nonlinear
interactions. PR-AUC fits the imbalanced alert task, while calibration, recall, lift, false alerts,
sector stability, and an untouched holdout prevent a single metric from dictating selection.

Conclude with judgment: the holdout shows meaningful ranking but modest precision and weaker
Utilities performance. The system is therefore an analyst prioritization tool with transparent KPI
evidence and uncertainty, not an automated credit decision or default model.
