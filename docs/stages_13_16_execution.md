# Stages 13–16 Execution Record

**Execution date:** 2026-08-02
**Modeling version:** `phase1-modeling-v1`
**Pipeline version:** `phase1-production-pipeline-v1`

## Stage 13 — KPI forecasting

The project compares random walk, random walk with drift, local level, local linear trend, and
regression DLM models at one- and four-quarter horizons. Each validation fold uses the last company
observation before the validation window as its origin. Models require 16 historical observations;
nonconvergence produces an explicit random-walk fallback.

One-quarter champions are random walk for free-cash-flow margin and interest coverage, and local
level for leverage. The four-quarter local-level model wins for all three KPIs, although its
advantage over random walk is modest. Four-quarter interval under-coverage is retained as a model
limitation rather than hidden by post-hoc widening.

Classifier forecast features use a prespecified local-level model for all KPIs. This prevents
forecast performance from later validation folds from influencing features used in earlier
classifier experiments.

## Stage 14 — deterioration classifiers

Regularized logistic regression and constrained gradient-boosted trees are evaluated across three
expanding folds and five feature increments: current fundamentals; history and peer context;
interest-coverage forecast; all KPI forecasts; and macro variables with limited interactions.
Preprocessing, probability calibration, and threshold selection are fitted inside each fold.
The experiment produces 6,810 out-of-fold model predictions for 681 unique validation decisions.

## Stage 15 — model selection

The gradient-boosted model with macro/interactions achieves the highest out-of-fold PR-AUC
(approximately 0.413) and is frozen as champion before holdout evaluation. The locked holdout
contains 457 labeled decisions. Overall PR-AUC is approximately 0.397, recall 0.563, precision
0.333, and top-decile lift 1.97. Utilities show weaker precision and calibration, which is explicitly
reported rather than obscured by pooled performance.

## Stage 16 — production engineering

The `run-stages-13-16` command rebuilds forecasts, classifier experiments, champion artifacts,
figures, checks, and run metadata from the certified local store without network calls. The Dagster
graph now has materializable assets from local source certification through production checks.
Forecast backtests are partitioned by fold and horizon; classifier predictions are partitioned by
fold. A smaller `--reuse-forecasts` refresh reruns classification, selection, figures, and checks
without repeating the more expensive state-space forecast stage.
Checks cover key uniqueness, chronology, finite forecasts, bounded probabilities, serialized model
presence, and figure-manifest completeness. Each run records configuration hashes, Git commit,
elapsed time, source scope, and stage summaries.

Generated analytical data and model binaries remain ignored by Git; reproducible code,
configuration, documentation, and publication figures are retained. The next stage is publication
delivery, not further tuning against the locked holdout.

## Publication figures

Stage 13, 14, and 15 figures are stored in separate numbered directories under
`reports/figures/`. Every plot uses `publication-theme-v1`, the established title prefix, and both
300-DPI PNG and editable SVG exports. Each directory contains a machine-readable figure manifest.
