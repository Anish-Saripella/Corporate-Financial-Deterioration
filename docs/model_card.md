# Phase 1 Deterioration Model Card

## Intended use

The model ranks currently listed Consumer Discretionary and Utilities companies by the probability
of a four-quarter deterioration in interest-coverage capacity. It supports research prioritization
and analyst watchlists. It does not estimate bankruptcy/default probability, approve credit, set
limits, or replace financial judgment.

## Development design

- Population: 60 certified companies, 30 per sector.
- Outcome: future interest coverage below 1.5 **and** at least 40% below its current level.
- Validation: three expanding-window folds with label-availability embargoes.
- Forecasts: random walk, drift, local level, local linear trend, and regression DLM at one- and
  four-quarter horizons.
- Classifiers: regularized logistic regression and constrained gradient-boosted trees across five
  prespecified feature increments.
- Calibration: a trailing four-quarter slice inside each training fold.
- Selection: out-of-fold PR-AUC first, followed by calibration, sector/time stability,
  interpretability, and simplicity.

The local-level model was prespecified for classifier forecast features before classifier
validation. KPI forecast champions are reported separately and do not retroactively determine
earlier classifier inputs.

## Selected model

The champion is gradient-boosted trees using historical, peer-relative, forecast, macroeconomic,
and limited interaction features. Development out-of-fold PR-AUC is approximately 0.413. The
selection record is hashed and persisted before the locked holdout is evaluated.

## Locked-holdout performance

| Slice | PR-AUC | Recall | Precision | Top-decile lift | Brier score |
|---|---:|---:|---:|---:|---:|
| Overall | 0.397 | 0.563 | 0.333 | 1.966 | 0.159 |
| Consumer Discretionary | 0.468 | 0.610 | 0.439 | 2.184 | 0.171 |
| Utilities | 0.332 | 0.486 | 0.225 | 2.153 | 0.147 |

The holdout alert rate is approximately 35%, above the 25% calibration-sample design constraint.
This is evidence of temporal/sector distribution shift, not a reason to retune on the holdout.
Operational thresholds must be selected later using capacity and cost assumptions on development
predictions only.

## Interpretation

Feature importance is descriptive, not causal. Sector-relative interest coverage, current
coverage, industry indicators, macro variables, and forecasted coverage change are prominent.
Analysts should inspect the underlying KPI history, forecast uncertainty, sector context, and data
quality flags for every alert.

## Limitations

- Survivorship bias: delisted companies are excluded.
- Two sectors and 60 companies limit generalization and uncertainty precision.
- Adjacent quarterly labels overlap; rows are not independent events.
- Non-vintage FRED availability uses a documented release-date proxy.
- State-space intervals under-cover for several four-quarter KPI forecasts.
- Utility alert precision and calibration are materially weaker than Consumer Discretionary.
- The model is a portfolio demonstration using free public data, not a validated bank risk model.
