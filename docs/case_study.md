# Case Study: Corporate Financial Deterioration Early Warning

## Business question

Can free public data identify currently listed companies whose capacity to service debt is likely
to deteriorate over the next four fiscal quarters, early enough to prioritize analyst review? The
project frames the task as a ranked early-warning problem rather than bankruptcy prediction,
because public quarterly fundamentals support the former more honestly.

## Approach

I constructed a filing-aware panel for 60 companies drawn reproducibly from Consumer
Discretionary and Utilities. SEC facts were normalized across XBRL tags and issuer fiscal calendars;
FRED/ALFRED variables were joined according to historical availability. Fourteen initially sampled
firms were replaced when strict three-KPI coverage, continuity, lineage, or denominator rules
failed. This produced 3,150 certified company-quarter observations with no detected temporal
leakage.

Three financial KPIs—interest coverage, free-cash-flow margin, and debt-to-assets—were forecast at
one- and four-quarter horizons. Random-walk and drift baselines were compared with local-level,
local-linear-trend, and regression state-space models. Forecast summaries, current fundamentals,
peer percentiles, macro variables, and limited sector interactions entered regularized logistic
regression and gradient-boosted tree challengers using three expanding-window folds.

## Result and decision

The selected gradient-boosted model achieved approximately 0.413 development OOF PR-AUC. On the
untouched 2023+ holdout it achieved 0.397 PR-AUC, 0.563 recall, 0.333 precision, and 1.966 top-decile
lift. Consumer Discretionary performance was stronger than Utilities, exposing a meaningful
generalization gap. The higher holdout alert rate was documented as distribution shift rather than
used to retune the model.

## Product and lessons

A Dagster asset graph, DuckDB/Parquet store, manifests, tests, model card, and published analytical
reports turn the analysis into a reproducible product. The reports connect portfolio aggregates,
company KPI histories, case reviews, and champion–challenger metrics. The most important
lesson is governance: point-in-time availability, fold-local preprocessing, a frozen label, and an
untouched holdout matter more than adding every possible model. The result is a credible screening
tool with explicit uncertainty and limitations, not a claim of default prediction.
